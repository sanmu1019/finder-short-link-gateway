# 安全说明

## 不应进入仓库的内容

请勿提交：

```text
.env
FINDER_API_KEY
FINDER_VNC_PASSWORD
WXSPH_COOKIE
WXSPH_COOKIES
登录二维码
HTTP Cookie
Authorization 请求头
objectNonceId 实际值
Chromium profile
日志和缓存
```

仓库中的 `.env.example` 只能包含占位符。

## 报告安全问题

不要在公开 issue 中提供：

- 可用 API Key。
- Cookie 或 token。
- 视频号账号信息。
- 完整请求和响应头。
- Chromium profile。
- 完整卡片 XML 或 nonce。

报告问题时仅提供脱敏后的状态码、错误类型和必要日志片段。

## 凭据泄漏处理

如果 API Key、Cookie 或 VNC 密码可能泄漏：

1. 立即更换对应凭据。
2. 重新创建相关容器。
3. 更新所有合法调用方。
4. 检查 Git 历史和日志。
5. 清除包含凭据的历史记录和公开缓存。

Finder Key 更新后：

```powershell
# 停止当前进程后重新启动
.\start_local.ps1
```

元宝 Cookie 更新后：

```powershell
# 停止当前进程后重新启动
.\start_wxsph_local.ps1
```

Docker/VPS 部署则需要重新创建对应容器。

## 本地部署

本地服务默认只监听：

```text
127.0.0.1:8790
127.0.0.1:8787
```

不要无必要改成 `0.0.0.0`。需要局域网访问时，应配置 Windows 防火墙来源限制。

## 公网部署

公网只建议暴露：

```text
POST /api/v1/finder/share-url
```

以下接口应保留在本机或管理网络：

```text
/ready
/api/v1/finder/reload
noVNC 6080
```

生产环境应增加：

- HTTPS。
- API 限流。
- 请求体大小限制。
- 独立用户密钥。
- 密钥撤销机制。
- 异常告警。
