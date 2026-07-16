from __future__ import annotations

import asyncio
import hmac
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from playwright.async_api import (
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    async_playwright,
)
from pydantic import BaseModel, Field


LOGGER = logging.getLogger("finder_gateway")
SPH_URL_RE = re.compile(
    r"^https://weixin\.qq\.com/sph/[A-Za-z0-9_-]+$"
)


@dataclass(frozen=True)
class Settings:
    api_key: str
    page_url: str
    profile_dir: Path
    headless: bool
    request_timeout: float
    startup_timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=os.getenv("FINDER_API_KEY", "").strip(),
            page_url=os.getenv(
                "FINDER_PAGE_URL",
                "https://channels.weixin.qq.com/platform/",
            ).strip(),
            profile_dir=Path(
                os.getenv(
                    "FINDER_PROFILE_DIR",
                    "/data/chromium-profile",
                )
            ),
            headless=os.getenv(
                "FINDER_BROWSER_HEADLESS",
                "false",
            ).lower()
            in {"1", "true", "yes"},
            request_timeout=float(
                os.getenv("FINDER_REQUEST_TIMEOUT", "25")
            ),
            startup_timeout=float(
                os.getenv("FINDER_STARTUP_TIMEOUT", "45")
            ),
        )


class ShareURLRequest(BaseModel):
    object_id: str = Field(min_length=1, max_length=256)
    object_nonce_id: str = Field(min_length=1, max_length=512)
    scene: int = Field(default=40, ge=1, le=1000)


class GatewayError(RuntimeError):
    pass


class GatewayNotReady(GatewayError):
    pass


class Gateway(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def status(self) -> dict[str, Any]: ...

    async def reload(self) -> None: ...

    async def share_url(
        self,
        object_id: str,
        object_nonce_id: str,
        scene: int,
    ) -> str: ...


SERVICE_STATUS_JS = """
() => {
  const chunks = window.webpackChunkfinder_helper_web;
  if (!Array.isArray(chunks)) {
    return {
      ready: false,
      reason: "webpack_runtime_not_loaded"
    };
  }

  try {
    let runtimeRequire =
      window.__FINDER_GATEWAY_WEBPACK_REQUIRE__;
    if (typeof runtimeRequire !== "function") {
      const chunkId = [
        "finder_gateway_status",
        Date.now(),
        Math.random().toString(36).slice(2)
      ].join("_");
      chunks.push([
        [chunkId],
        {},
        (capturedRequire) => {
          runtimeRequire = capturedRequire;
          window.__FINDER_GATEWAY_WEBPACK_REQUIRE__ =
            capturedRequire;
        }
      ]);
    }

    if (typeof runtimeRequire !== "function") {
      return {
        ready: false,
        reason: "webpack_require_not_captured"
      };
    }

    try {
      runtimeRequire(39658);
    } catch (_) {}

    const locate = (value, depth = 0, seen = new Set()) => {
      if (
        value == null ||
        depth > 3 ||
        (typeof value !== "object" &&
          typeof value !== "function") ||
        seen.has(value)
      ) {
        return null;
      }
      seen.add(value);
      if (
        typeof value.getObjectShortLink === "function"
      ) {
        return value;
      }
      for (const key of [
        "WY",
        "default",
        "service",
        "api",
        "finderService"
      ]) {
        const found = locate(
          value[key],
          depth + 1,
          seen
        );
        if (found) return found;
      }
      return null;
    };

    let service = locate(
      window.__FINDER_GATEWAY_SHORT_LINK_SERVICE__
    );

    if (!service) {
      try {
        service = locate(runtimeRequire(91847));
      } catch (_) {}
    }

    if (!service && runtimeRequire.m) {
      const moduleIds = Object.keys(runtimeRequire.m);
      for (const moduleId of moduleIds) {
        let source = "";
        try {
          source = String(runtimeRequire.m[moduleId]);
        } catch (_) {
          continue;
        }
        if (!source.includes("getObjectShortLink")) {
          continue;
        }
        try {
          service = locate(runtimeRequire(moduleId));
        } catch (_) {
          service = null;
        }
        if (service) break;
      }
    }

    if (!service) {
      return {
        ready: false,
        reason: "short_link_service_not_found"
      };
    }

    window.__FINDER_GATEWAY_SHORT_LINK_SERVICE__ =
      service;
    return {
      ready: true,
      reason: ""
    };
  } catch (error) {
    return {
      ready: false,
      reason:
        error && error.message
          ? String(error.message).slice(0, 160)
          : "service_probe_failed"
    };
  }
}
"""


SHARE_URL_JS = """
async ({ objectId, nonceId, scene }) => {
  const statusProbe = %s;
  const status = statusProbe();
  if (!status.ready) {
    throw new Error(status.reason || "gateway_not_ready");
  }

  const service =
    window.__FINDER_GATEWAY_SHORT_LINK_SERVICE__;
  const result = await service.getObjectShortLink({
    exportId: String(objectId),
    nonceId: String(nonceId),
    scene: Number(scene) || 40
  });
  const data =
    result && typeof result.data === "object"
      ? result.data
      : result || {};
  const shareUrl =
    data.shortUrl ||
    data.feedH5Url ||
    data.shareUrl ||
    "";
  if (!shareUrl) {
    const code =
      data.errCode ??
      data.errorCode ??
      result?.errCode ??
      "unknown";
    throw new Error(
      "short_link_response_missing_url:" + code
    );
  }
  return {
    sphUrl: String(shareUrl),
    errCode:
      data.errCode ??
      data.errorCode ??
      result?.errCode ??
      null
  };
}
""" % SERVICE_STATUS_JS


class PlaywrightGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._lock = asyncio.Lock()
        self._last_error = ""
        self._started_at = 0.0

    async def start(self) -> None:
        async with self._lock:
            if self._context is not None:
                return
            self.settings.profile_dir.mkdir(
                parents=True,
                exist_ok=True,
            )
            self._playwright = await async_playwright().start()
            try:
                self._context = (
                    await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=str(
                            self.settings.profile_dir
                        ),
                        headless=self.settings.headless,
                        locale="zh-CN",
                        viewport=None,
                        ignore_default_args=[
                            "--enable-automation"
                        ],
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-dev-shm-usage",
                            "--no-sandbox",
                            "--start-maximized",
                        ],
                    )
                )
                self._page = (
                    self._context.pages[0]
                    if self._context.pages
                    else await self._context.new_page()
                )
                self._page.set_default_timeout(
                    self.settings.request_timeout * 1000
                )
                await asyncio.wait_for(
                    self._page.goto(
                        self.settings.page_url,
                        wait_until="domcontentloaded",
                    ),
                    timeout=self.settings.startup_timeout,
                )
                self._started_at = time.time()
                self._last_error = ""
            except Exception:
                await self._stop_unlocked()
                raise

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_unlocked()

    async def _stop_unlocked(self) -> None:
        context = self._context
        playwright = self._playwright
        self._context = None
        self._page = None
        self._playwright = None
        if context is not None:
            try:
                await context.close()
            except PlaywrightError:
                pass
        if playwright is not None:
            try:
                await playwright.stop()
            except PlaywrightError:
                pass

    async def _ensure_page_unlocked(self) -> Page:
        if self._context is None:
            raise GatewayNotReady("browser_not_started")
        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()
            self._page.set_default_timeout(
                self.settings.request_timeout * 1000
            )
            await self._page.goto(
                self.settings.page_url,
                wait_until="domcontentloaded",
            )
        return self._page

    async def status(self) -> dict[str, Any]:
        async with self._lock:
            if self._context is None:
                return {
                    "browser_started": False,
                    "ready": False,
                    "reason": self._last_error
                    or "browser_not_started",
                    "uptime_seconds": 0,
                }
            try:
                page = await self._ensure_page_unlocked()
                probe = await asyncio.wait_for(
                    page.evaluate(SERVICE_STATUS_JS),
                    timeout=self.settings.request_timeout,
                )
                ready = bool(probe.get("ready"))
                reason = str(probe.get("reason") or "")
                if not ready:
                    self._last_error = reason
                return {
                    "browser_started": True,
                    "ready": ready,
                    "reason": reason,
                    "page_host": "channels.weixin.qq.com",
                    "uptime_seconds": max(
                        0,
                        int(time.time() - self._started_at),
                    ),
                }
            except Exception as exc:
                self._last_error = _safe_error(exc)
                return {
                    "browser_started": True,
                    "ready": False,
                    "reason": self._last_error,
                    "page_host": "channels.weixin.qq.com",
                    "uptime_seconds": max(
                        0,
                        int(time.time() - self._started_at),
                    ),
                }

    async def reload(self) -> None:
        async with self._lock:
            page = await self._ensure_page_unlocked()
            await asyncio.wait_for(
                page.goto(
                    self.settings.page_url,
                    wait_until="domcontentloaded",
                ),
                timeout=self.settings.startup_timeout,
            )
            self._last_error = ""

    async def share_url(
        self,
        object_id: str,
        object_nonce_id: str,
        scene: int,
    ) -> str:
        async with self._lock:
            page = await self._ensure_page_unlocked()
            try:
                result = await asyncio.wait_for(
                    page.evaluate(
                        SHARE_URL_JS,
                        {
                            "objectId": object_id,
                            "nonceId": object_nonce_id,
                            "scene": scene,
                        },
                    ),
                    timeout=self.settings.request_timeout,
                )
            except Exception as exc:
                self._last_error = _safe_error(exc)
                raise GatewayNotReady(
                    self._last_error
                ) from exc

            share_url = str(result.get("sphUrl") or "")
            if not SPH_URL_RE.fullmatch(share_url):
                self._last_error = (
                    "management_page_returned_invalid_sph_url"
                )
                raise GatewayError(self._last_error)
            self._last_error = ""
            LOGGER.info(
                "short link generated object_id=%s nonce_length=%d scene=%d",
                object_id,
                len(object_nonce_id),
                scene,
            )
            return share_url


def _safe_error(exc: Exception) -> str:
    text = str(exc).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:240] or exc.__class__.__name__


def create_app(
    settings: Settings | None = None,
    gateway: Gateway | None = None,
) -> FastAPI:
    active_settings = settings or Settings.from_env()
    active_gateway = gateway or PlaywrightGateway(
        active_settings
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        startup_error = ""
        try:
            await active_gateway.start()
        except Exception as exc:
            startup_error = _safe_error(exc)
            LOGGER.exception(
                "browser startup failed: %s",
                startup_error,
            )
        app.state.startup_error = startup_error
        try:
            yield
        finally:
            await active_gateway.stop()

    app = FastAPI(
        title="Finder Short-Link Gateway",
        version="1.0.0",
        lifespan=lifespan,
    )

    async def require_api_key(
        x_api_key: str | None = Header(
            default=None,
            alias="X-API-Key",
        ),
        authorization: str | None = Header(default=None),
    ) -> None:
        expected = active_settings.api_key
        if not expected:
            raise HTTPException(
                status_code=503,
                detail="FINDER_API_KEY is not configured",
            )
        bearer = ""
        if authorization and authorization.lower().startswith(
            "bearer "
        ):
            bearer = authorization[7:].strip()
        supplied = x_api_key or bearer
        if not supplied or not hmac.compare_digest(
            supplied,
            expected,
        ):
            raise HTTPException(
                status_code=401,
                detail="invalid API key",
            )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        state = await active_gateway.status()
        return {
            "code": 0,
            "msg": "ok",
            "data": {
                "service": "finder-short-link-gateway",
                "version": app.version,
                **state,
            },
        }

    @app.get(
        "/ready",
        dependencies=[Depends(require_api_key)],
    )
    async def ready() -> dict[str, Any]:
        state = await active_gateway.status()
        if not state.get("ready"):
            raise HTTPException(
                status_code=503,
                detail=state.get("reason")
                or "management page is not ready",
            )
        return {
            "code": 0,
            "msg": "ready",
            "data": state,
        }

    async def resolve_share_url(
        object_id: str,
        object_nonce_id: str,
        scene: int,
    ) -> dict[str, Any]:
        try:
            share_url = await active_gateway.share_url(
                object_id.strip(),
                object_nonce_id.strip(),
                scene,
            )
        except GatewayNotReady as exc:
            raise HTTPException(
                status_code=503,
                detail=str(exc),
            ) from exc
        except GatewayError as exc:
            raise HTTPException(
                status_code=502,
                detail=str(exc),
            ) from exc
        return {
            "code": 0,
            "msg": "ok",
            "data": {
                "object_id": object_id.strip(),
                "sph_url": share_url,
                "feedH5Url": share_url,
                "scene": scene,
            },
        }

    @app.get(
        "/api/v1/finder/share-url",
        dependencies=[Depends(require_api_key)],
    )
    async def finder_share_url(
        object_id: str = Query(min_length=1),
        object_nonce_id: str = Query(min_length=1),
        scene: int = Query(default=40, ge=1, le=1000),
    ) -> dict[str, Any]:
        return await resolve_share_url(
            object_id,
            object_nonce_id,
            scene,
        )

    @app.post(
        "/api/v1/finder/share-url",
        dependencies=[Depends(require_api_key)],
    )
    async def finder_share_url_post(
        body: ShareURLRequest,
    ) -> dict[str, Any]:
        return await resolve_share_url(
            body.object_id,
            body.object_nonce_id,
            body.scene,
        )

    @app.post(
        "/api/v1/finder/reload",
        dependencies=[Depends(require_api_key)],
    )
    async def reload_page() -> dict[str, Any]:
        try:
            await active_gateway.reload()
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=_safe_error(exc),
            ) from exc
        return {
            "code": 0,
            "msg": "reloaded",
        }

    return app


app = create_app()
