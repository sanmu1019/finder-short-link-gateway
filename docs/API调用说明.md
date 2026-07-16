# API 调用说明

## 本地地址

默认本地接口：

```text
http://127.0.0.1:8790/api/v1/finder/share-url
```

调用前确认：

```powershell
curl.exe http://127.0.0.1:8790/health
```

并确认返回结果中的 `ready` 为 `true`。

## 参数来源

视频号卡片原始 XML 通常包含：

```xml
<objectId>OBJECT_ID</objectId>
<objectNonceId>OBJECT_NONCE_ID</objectNonceId>
```

调用方需要从机器人消息回调、消息接口或原始卡片 XML 中提取这两个字段。
普通微信界面通常不会直接显示完整 `objectNonceId`。

两个字段必须来自同一张卡片：

```text
objectId -> object_id
objectNonceId -> object_nonce_id
```

不要猜测 nonce，也不要只传作品页面中显示的数值 ID。

## 推荐 POST 接口

```text
POST /api/v1/finder/share-url
```

请求头：

```text
X-API-Key: YOUR_API_KEY
Content-Type: application/json
```

请求体：

```json
{
  "object_id": "OBJECT_ID",
  "object_nonce_id": "OBJECT_NONCE_ID",
  "scene": 40
}
```

### PowerShell

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

### Python

```python
import requests


response = requests.post(
    "http://127.0.0.1:8790/api/v1/finder/share-url",
    headers={
        "X-API-Key": "YOUR_API_KEY",
    },
    json={
        "object_id": "OBJECT_ID",
        "object_nonce_id": "OBJECT_NONCE_ID",
        "scene": 40,
    },
    timeout=45,
)

print(response.status_code)
print(response.json())
```

### curl

在 Git Bash、Linux 或 macOS 中：

```bash
curl -X POST \
  'http://127.0.0.1:8790/api/v1/finder/share-url' \
  -H 'X-API-Key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  --data '{
    "object_id": "OBJECT_ID",
    "object_nonce_id": "OBJECT_NONCE_ID",
    "scene": 40
  }'
```

## 成功响应

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

推荐读取：

```text
data.sph_url
```

响应不会回显 `object_nonce_id`。

## 兼容 GET 接口

服务保留 GET 形式，供已有机器人兼容：

```text
GET /api/v1/finder/share-url
```

示例：

```python
response = requests.get(
    "http://127.0.0.1:8790/api/v1/finder/share-url",
    headers={"X-API-Key": "YOUR_API_KEY"},
    params={
        "object_id": "OBJECT_ID",
        "object_nonce_id": "OBJECT_NONCE_ID",
        "scene": 40,
    },
    timeout=45,
)
```

新代码应使用 POST。GET 会把 nonce 放进 URL 查询参数，可能进入代理或客户端
日志。

## 健康检查

无需 API Key：

```text
GET /health
```

```powershell
curl.exe http://127.0.0.1:8790/health
```

就绪状态：

```json
{
  "data": {
    "browser_started": true,
    "ready": true,
    "reason": ""
  }
}
```

## 重新加载管理页面

```text
POST /api/v1/finder/reload
```

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8790/api/v1/finder/reload" `
  -Headers @{"X-API-Key" = "YOUR_API_KEY"}
```

该接口用于管理后台页面异常或登录状态更新后的重新加载，不应暴露给不受信任的
调用方。

## 错误码

### 401

```json
{
  "detail": "invalid API key"
}
```

检查 `X-API-Key` 是否与 `.env` 中的 `FINDER_API_KEY` 一致。

### 422

请求参数缺失、为空或格式不符合接口限制。

### 503

Chromium 未启动、管理后台未登录或短链模块尚未就绪。

### 502

管理后台没有返回有效短链。常见原因是卡片参数不匹配，或管理后台前端接口发生
变化。

## 可选 sph 解析接口

启用 `start_wxsph_local.ps1` 后：

```text
GET http://127.0.0.1:8787/api/wxsph
```

示例：

```powershell
curl.exe --get `
  -H "X-API-Key: YOUR_WXSPH_KEY" `
  --data-urlencode "url=https://weixin.qq.com/sph/SHORT_CODE" `
  "http://127.0.0.1:8787/api/wxsph"
```

该接口使用元宝解析。Finder 短链生成接口本身不使用元宝。

## 远程部署时的地址替换

只有将项目部署到 Docker/VPS 并配置 HTTPS 反向代理后，才把：

```text
http://127.0.0.1:8790
```

替换为类似：

```text
https://sph.example.com
```

不要直接把 Uvicorn、健康检查、reload 或 noVNC 端口暴露到公网。

## 调用限制

- 不进行高并发压力测试。
- 不枚举 object ID。
- 不记录或公开完整 nonce。
- 不把 API Key 放进 URL。
- 建议客户端超时设置为 45 秒。
- 同一网关按串行方式操作一个 Chromium 页面。
