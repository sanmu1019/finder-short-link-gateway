# 视频号卡片短链网关

通过已登录的视频号管理后台，将微信视频号卡片中的
`objectId + objectNonceId` 转换为：

```text
https://weixin.qq.com/sph/...
```

仓库默认按 **Windows 本地部署** 使用：

- Python 运行 FastAPI 网关。
- Playwright 自动打开桌面 Chromium。
- 用户在本机扫码登录视频号管理后台。
- 登录状态保存在本地 `data/chromium-profile`。
- 机器人或本机程序调用 `127.0.0.1:8790`。

Docker、VPS、noVNC 和 Nginx 仅作为可选部署方式。

## 使用边界

本项目复用登录后的视频号管理后台前端模块，不是微信公开 API。

请只处理自己管理或已经获得授权的账号与内容，并自行确认平台规则。该服务采用
单浏览器串行调用模型，适合个人机器人和小规模自动化，不适合作为匿名、高并发
或无限制的公共接口。

## 工作流程

```text
视频号卡片 XML
-> 提取 objectId + objectNonceId
-> 本地 Finder 网关
-> 已登录的管理后台 Chromium
-> webpack getObjectShortLink
-> https://weixin.qq.com/sph/...
```

可选解析流程：

```text
sph
-> wxsph-api
-> 元宝解析接口
-> 视频信息
```

**短链生成不使用元宝。** 只有主动启用可选 `wxsph-api` 时，才需要元宝
Cookie。

## 本地快速开始

### 1. 环境要求

建议使用：

```text
Windows 10/11
Python 3.12+
Git
```

确认 Python 可用：

```powershell
python --version
```

### 2. 获取和安装

```powershell
git clone YOUR_REPOSITORY_URL
cd finder-short-link-gateway
powershell -ExecutionPolicy Bypass -File .\setup_local.ps1
```

安装脚本会：

1. 创建 `.venv`。
2. 安装 Finder 网关依赖。
3. 安装 Playwright Chromium。
4. 在首次运行时从 `.env.example` 创建 `.env`。

### 3. 配置

编辑仓库根目录的 `.env`，至少替换：

```dotenv
FINDER_API_KEY=change_me_to_a_long_random_key
```

`FINDER_API_KEY` 用于保护本地接口。不要提交或公开 `.env`。

本地运行使用：

```dotenv
FINDER_BROWSER_HEADLESS=false
FINDER_PROFILE_DIR=./data/chromium-profile
```

本地脚本默认监听 8790；如需更换端口，使用
`.\start_local.ps1 -Port 8791`。

### 4. 启动和扫码

```powershell
powershell -ExecutionPolicy Bypass -File .\start_local.ps1
```

Chromium 会直接在桌面打开：

1. 扫码登录视频号管理后台。
2. 进入内容管理页面。
3. 打开一次作品的分享菜单，让页面加载短链模块。
4. 保持 Chromium 和 PowerShell 窗口运行。

检查状态：

```powershell
curl.exe http://127.0.0.1:8790/health
```

就绪时应包含：

```json
{
  "data": {
    "browser_started": true,
    "ready": true,
    "reason": ""
  }
}
```

如果 `ready` 为 `false`，先确认登录状态，再进入内容管理页面并重新打开一次
分享菜单。

### 5. 调用接口

PowerShell：

```powershell
$headers = @{
  "X-API-Key" = "YOUR_API_KEY"
}

$body = @{
  object_id = "OBJECT_ID"
  object_nonce_id = "OBJECT_NONCE_ID"
  scene = 40
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8790/api/v1/finder/share-url" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

成功结果：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "object_id": "OBJECT_ID",
    "sph_url": "https://weixin.qq.com/sph/SHORT_CODE",
    "feedH5Url": "https://weixin.qq.com/sph/SHORT_CODE",
    "scene": 40
  }
}
```

`objectId` 和 `objectNonceId` 必须来自同一张视频号卡片的原始 XML。完整说明见
[API调用说明](docs/API调用说明.md)。

## 停止和再次启动

在运行网关的 PowerShell 窗口按 `Ctrl+C` 停止。

再次启动：

```powershell
.\start_local.ps1
```

登录状态保存在：

```text
data/chromium-profile
```

正常停止不会清除登录状态。若登录过期，在自动打开的 Chromium 中重新扫码即可。

## 可选元宝解析器

该组件把已经生成的 `sph` 链接解析为标题、作者、封面和媒体候选地址。它依赖
元宝会话，Cookie 可能过期。

在 `.env` 中配置：

```dotenv
WXSPH_API_KEYS=change_me_to_a_long_random_key
WXSPH_COOKIE=
WXSPH_HOST_PORT=8787
```

启动：

```powershell
.\start_wxsph_local.ps1
```

检查：

```powershell
curl.exe http://127.0.0.1:8787/health
```

启用该组件时必须配置 `WXSPH_API_KEYS`。不需要解析视频信息时，不要配置 Cookie，
也不要启动该组件。

## 可选 Docker 或 VPS 部署

仓库保留：

- `docker-compose.yml`
- `deploy.sh`
- Finder 网关 Dockerfile
- noVNC 登录环境
- Nginx 反向代理示例

这些文件不影响本地部署。只有需要让远程机器人跨机器调用时，才需要考虑
Docker/VPS。详细步骤见[本地部署指南](docs/本地部署指南.md)中的可选章节。

## 目录结构

```text
.
├── .env.example
├── README.md
├── SECURITY.md
├── setup_local.ps1
├── start_local.ps1
├── start_wxsph_local.ps1
├── docker-compose.yml
├── docs/
│   ├── API调用说明.md
│   ├── 本地部署指南.md
│   ├── 开发与测试说明.md
│   └── 架构与工作原理.md
├── finder_gateway/
│   ├── app/
│   │   └── main.py
│   └── tests/
├── nginx/
└── wxsph_api/
```

## 测试

测试使用 FakeGateway，不会启动真实 Chromium，也不会访问视频号接口：

```powershell
.\.venv\Scripts\python.exe -m pip install pytest httpx
.\.venv\Scripts\python.exe -m pytest -q finder_gateway\tests
```

## 安全

- 不提交 `.env`、Cookie、token、二维码、日志或浏览器 profile。
- 不记录或公开完整 `objectNonceId`。
- API Key 只通过请求头发送，不放在 URL 中。
- 本地服务默认只监听 `127.0.0.1`。
- 公网部署必须额外配置 HTTPS、限流和密钥撤销机制。

安全问题处理方式见 [SECURITY.md](SECURITY.md)。

## 文档

- [本地部署指南](docs/本地部署指南.md)
- [API调用说明](docs/API调用说明.md)
- [架构与工作原理](docs/架构与工作原理.md)
- [开发与测试说明](docs/开发与测试说明.md)

## 许可证

当前仓库模板未预设开源许可证。公开发布前，请根据实际用途添加合适的
`LICENSE` 文件。
