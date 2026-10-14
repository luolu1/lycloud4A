# JumpServer 对接方案

> 适用系统：lycloud4A 4A 平台（本仓库）
> 对接对象：JumpServer 开源堡垒机（v3 / v4 LTS）
> 文档版本：v1.0
> 说明：本文档同时面向**运维人员**（可直接照做的配置步骤）与**研发人员**（需要二次开发的接口规范）。

---

## 1. 文档目的

本文给出 lycloud4A 与 JumpServer 的完整对接方案，覆盖四类对接：

| 编号 | 对接方向 | 说明 | 落地状态 |
|------|----------|------|----------|
| 一 | **资产纳管** | 把 JumpServer 作为堡垒机资产纳入 4A 统一管理、授权、审计 | ✅ 平台现有能力 |
| 二 | **单点登录（SSO）** | 用户从 4A 免登进入 JumpServer（或 JumpServer 以 4A 为身份源） | 🚧 需二次开发（见 §6） |
| 三 | **账号 / 组织同步** | 4A 与 JumpServer 的用户、组织、资产对齐 | 🚧 需二次开发（见 §7） |
| 四 | **审计数据对接** | 4A 与 JumpServer 的审计日志统一留存 / 汇聚 | ⚙️ 部分现有 + 部分需开发（见 §8） |

> 图例：✅ 现有能力（照做即可）｜🚧 需二次开发（含接口规范）｜⚙️ 可选 / 增量

---

## 2. 术语

| 术语 | 含义 |
|------|------|
| 4A | 认证（Authentication）、授权（Authorization）、账号（Account）、审计（Audit） |
| 纳管对象 / 设备 | 4A 中统一管理的资产，模型为 `applications` 表（含网络设备、服务器、应用、堡垒机等） |
| 连接工具 | 本地可执行程序（MobaXterm / WinSCP / Chrome 等），由连接助手 `lycloud4A` 拉起 |
| 连接助手 | 本平台的本地客户端 `lycloud4A.exe`，负责解析票据、拉起工具、回传会话日志 |
| 一次性票据 | `POST /apps/{id}/connect` 签发的 60 秒有效 ticket，供助手解析凭证 |
| IdP / SP | 身份提供方 / 服务提供方 |
| X-Pack | JumpServer 企业版增强包 |

---

## 3. 总体对接架构

```
                    ┌────────────────────────────────────────────┐
                    │              lycloud4A 4A 平台             │
                    │  账号/组织  ·  认证  ·  授权/策略  ·  审计   │
                    │  applications（纳管对象，含 JumpServer）    │
                    └───────┬───────────────┬───────────────┬────┘
                            │               │               │
              ① 资产纳管/授权 │    ② SSO 跳转  │   ④ 审计汇聚  │
                            │               │               │
                            ▼               ▼               ▼
                    ┌────────────────────────────────────────────┐
                    │            JumpServer 堡垒机 (SP)          │
                    │  用户 · 资产 · 授权 · 会话/命令审计         │
                    └───────┬───────────────────────────┬────────┘
                            │ ③ 账号/资产同步（REST API）│
                            └───────────────────────────┘
```

- **控制面**：4A 负责「谁，能访问什么」；JumpServer 负责「访问过程的安全与录屏审计」。
- **建议**：4A 作为统一入口与身份源，JumpServer 作为被纳管的运维通道，二者审计互为补充。

---

## 4. 前置条件与信息收集

### 4.1 环境要求

| 项 | 要求 |
|----|------|
| 4A 平台 | 本仓库后端可访问（默认 `http://<4a-host>:8000`），拥有 `admin` 或具备 `application:write` / `application:read` 的账号 |
| JumpServer | 可访问其 Web 与 REST API：`http://<jumpserver>/api/docs` 可打开 |
| 连接助手 | 终端用户机器安装 `lycloud4A` 连接助手（连接工具页可下载） |
| 网络 | 4A 后端 → JumpServer（用于连通性检测 / API 同步）；用户终端 → JumpServer（用于实际运维） |

### 4.2 信息收集清单（对接前填好）

| 变量 | 示例 | 用途 |
|------|------|------|
| `JMS_URL` | `https://jumpserver.example.com` | JumpServer 访问地址 |
| `JMS_API_USER` | `api-bot` | 用于调用 API 的专用账号 |
| `JMS_API_PASS` | `************` | 该账号密码（或 Private Token / Access Key） |
| `JMS_ORG_ID` | `00000000-0000-0000-0000-000000000002` | 组织 ID（多组织时必填，请求头 `X-JMS-ORG`） |
| 4A 纳管协议 | `https`（Web 门户）或 `ssh`（跳板入口） | 决定连接工具与端口 |
| 4A 纳管地址 | `jumpserver.example.com` | 写入 `applications.url` |

> **安全提醒**：JumpServer 官方安全公告（JS-2026.09.09）指出 Access Key 越权泄露风险，请确保 **V3 ≥ v3.10.23 LTS、V4 ≥ v4.10.19 LTS**，并优先使用 Private Token 而非长期密码调用 API。

---

## 5. 对接方式一：资产纳管（✅ 现有能力，运维可直接操作）

目标：在 4A 中建立 JumpServer 纳管对象，做到**统一入口、统一授权、统一留痕**。

### 5.1 创建纳管对象

**UI 路径**：登录 4A → 左侧「授权管理 / 设备系统」→ 「新增」。

**关键字段**：

| 字段 | 建议值 | 说明 |
|------|--------|------|
| 名称 | `堡垒机 JumpServer` | 展示名 |
| 编码 `code` | `JUMP` | 全局唯一；种子数据已内置该对象 |
| 类型 `app_type` | `bastion` | 堡垒机类型 |
| 协议 `protocol` | `https`（Web 门户）/ `ssh`（命令行入口） | 决定可用连接工具与默认端口 |
| 地址 `url` | `jumpserver.example.com` 或 `https://jumpserver.example.com` | 连通性检测与跳转目标 |
| 登录用户 | `ops` / 指定账号 | 展示用，实际凭证走密码托管 |
| 凭证 | 密码 / SSH 密钥 | 加密存储于 `applications.credential_encrypted` |
| 负责人 | `运维中心` | 责任归属 |

**等价的 API 调用**：

```bash
curl -X POST "http://<4a-host>:8000/api/v1/apps" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "堡垒机 JumpServer",
    "code": "JUMP",
    "app_type": "bastion",
    "protocol": "https",
    "url": "https://jumpserver.example.com",
    "login_username": "ops",
    "credential_type": "password",
    "credential": "Jump@Server2024",
    "owner": "运维中心",
    "description": "运维堡垒机，所有设备访问经此审计",
    "status": true
  }'
```

> 字段定义见 [`docs/api-contract.md`](api-contract.md) 的「授权 /apps」一节与 `backend/app/schemas/application.py`。

### 5.2 协议与连接工具矩阵

平台内置连接工具（`launch_tools` 表）支持的协议：

| 工具 | kind | 支持协议 |
|------|------|----------|
| MobaXterm | `mobaxterm` | ssh, telnet, rsh, mosh, rdp, vnc, xdmcp, sftp, ftp, scp, serial |
| NetCatty | `netcatty` | ssh, serial |
| Xshell | `xshell` | ssh, telnet, rlogin, serial |
| SecureCRT | `securecrt` | ssh, telnet, rlogin, serial |
| WinSCP | `winscp` | sftp, scp, ftp, ftps |
| Chrome | `chrome` | http, https, oidc, saml, web |

**纳管协议选择建议**：

| 访问方式 | `protocol` | 可用工具 |
|----------|-----------|----------|
| 浏览器打开 JumpServer Web 门户 | `https` | Chrome |
| 直接 SSH 登录跳板 shell | `ssh` | MobaXterm / Xshell / SecureCRT / NetCatty |
| 文件传输（如经跳板传文件） | `sftp` | WinSCP / MobaXterm |

> 只有当 `tool.protocols` 包含设备的 `protocol` 时，「连接」下拉才会出现该工具；否则按钮置灰。协议矩阵由后端 `connect_app` 校验，不匹配会返回 `400`。

### 5.3 授权配置

平台支持三层授权，按最小权限原则配置：

1. **设备授权用户**（直接授权）
   - `POST /apps/{id}/users` `{"user_ids": [..]}`（覆盖式）
   - `DELETE /apps/{id}/users/{user_id}`（移除）
2. **角色授权**：为用户分配带 `application:read` / `policy:*` 的角色。
3. **访问策略**（`policies`）：按主体（用户/组/角色/组织）、资源（application）与动作（`read` / `launch` / `connect`）配置 `allow` / `deny`，可先通过 `POST /policies/evaluate` 试算。

> **建议**：为「运维组」授予 JumpServer 设备的 `read`，为「运维管理员」额外授予 `write`；对敏感目标设备用 `deny` 显式收敛。

### 5.4 发起访问

**方式 A：本地工具直连（✅ 现有，已完整审计）**

1. 用户在「设备系统」找到 JumpServer，点击「连接」→ 选择工具（如 MobaXterm / Chrome）。
2. 前端调用 `POST /api/v1/apps/{id}/connect`，后端签发 60 秒一次性票据，并写入一条**连接审计**。
3. 前端把票据交给本地助手 `POST http://127.0.0.1:47621/connect`；助手调用 `POST /api/v1/apps/connect/resolve` 解析票据，拿到解密后的凭证并拉起工具。
4. 终端会话过程由助手按 2 秒轮询切分回传 `POST /api/v1/apps/connect/upload-log`，后端渲染为可读 `.log`。

**方式 B：SSO 跳转（⚠️ 现状为简化实现，见 §6）**

- `POST /api/v1/apps/{id}/launch` 会在 `url` 后拼接 `?ticket=<uuid>` 返回 `redirect_url`，并记录一条「启动应用」审计。
- **注意**：JumpServer 本身**不会**解析该 `ticket`，因此当前该接口只是「带票据打开 JumpServer 登录页」的占位实现，**并不构成真正的免登**。真正的单点登录请见 §6。

### 5.5 连通性检测

- `POST /api/v1/apps/{id}/check`：后端按协议默认端口做 TCP 探测。
- 协议默认端口（`backend/app/services/device_service.py`）：`ssh/sftp=22`、`ftp=21`、`https=443`、`http=80`、`rdp=3389`、`vnc=5900`、`cas/oidc/saml=443`。
- 若 `url` 为网段（含 `/`）或无固定端口协议，会返回 `unreachable`（`地址为网段或协议无固定端口，无法单点探测`），属预期行为。

### 5.6 审计留痕（现有）

| 操作 | 审计 `category` | `action` |
|------|----------------|----------|
| 发起连接（含助手解析） | `connection` | `<协议>连接`，如 `ssh连接` / `https连接` |
| 启动应用（launch） | `admin` | `启动应用` |
| 授权用户变更 | `authz` | `更新设备授权用户` / `移除设备授权用户` |
| 新增/更新/移除设备 | `authz` / `admin` | `新增设备` / `更新设备` / `移除设备` |

- **原则**：一次连接**只产生一条** `connection` 审计行（助手解析票据时不再重复留痕）。
- `detail` 中记录：设备类型、连接工具、连接协议、访问 IP、会话标识；会话日志路径在助手回传后写入。
- 会话日志正文：`GET /api/v1/audits/{id}/log-content`。

---

## 6. 对接方式二：单点登录（SSO）

> 本节区分「最短落地路径」与「4A 作为统一身份源的完整路径」。请按改造意愿选择。

### 6.1 现状说明（重要）

- 4A 平台**当前没有** OIDC / CAS / SAML / LDAP 服务端接口，`applications.protocol` 中的 `oidc/saml/cas` 目前只是**协议标签**，用于选择连接工具与展示。
- `POST /apps/{id}/launch` 为**简化跳转**，仅拼接 ticket，JumpServer 无法消费，**不等于免登**。
- 因此，真 SSO 必须走下面三条路径之一。

### 6.2 方案对比

| 方案 | 身份源 | 需要改动 | 落地难度 | 适用场景 |
|------|--------|----------|----------|----------|
| **A. 4A 作为 IdP** | lycloud4A | 4A 新增 OIDC/CAS IdP 接口（🚧） | 高 | 要求 4A 为唯一身份源 |
| **B. 复用企业 IdP** | 已有 Keycloak / ADFS / Azure AD / 竹云 IDaaS 等 | 仅两侧配置（✅） | 低 | 已有统一身份平台，最快落地 |
| **C. SP 发起 + 桥接** | 企业 IdP 中转 | 4A 提供身份 API，桥接方同步 | 中 | 4A 不便直接当 IdP |

### 6.3 方案 B（推荐先行）：JumpServer 对接企业 IdP

这是**无需改 4A** 即可获得 SSO 的路径：让 JumpServer 与企业 IdP 对接，4A 侧仍以「纳管 + 跳转」把它们串起来。

#### B-1. JumpServer 侧配置（OIDC，X-Pack）

**路径**：JumpServer → 右上角头像 →「系统设置」→「认证设置」→「OIDC」。

| 参数 | 说明 |
|------|------|
| 启用 OIDC 认证 | 勾选 |
| Base site URL | JumpServer 完整域名，如 `https://jumpserver.example.com`（用于拼回调地址） |
| 客户端 ID / 客户端密钥 | IdP 侧分配 |
| 端点地址 / 授权端点 / token 端点 / jwks 端点 / 用户信息端点 | IdP 的 Discovery 信息 |
| 签名算法 | `RS256` |
| 连接范围 | `openid`（按需加 `email profile`） |
| 总是更新用户信息 | 建议勾选 |
| 忽略 SSL 证书验证 | 生产建议**不**勾选 |

**回调地址（在 IdP 侧登记）**：`https://<jumpserver>/core/auth/oidc/callback/`（以实际版本提示为准，配置页会显示）。

#### B-2. JumpServer 侧配置（CAS）

**路径**：「系统设置」→「认证设置」→「CAS 认证」。

| 参数 | 说明 |
|------|------|
| 启用 CAS 认证 | 勾选 |
| 服务端地址 | IdP 的 CAS server，如 `https://idp.example.com/cas` |
| 代理服务地址 | JumpServer 访问地址 |
| 版本 | `1` / `2` / `3`（推荐 3） |
| 同步注销 | 按需；注销 JumpServer 时同步注销 IdP 会话 |
| 用户名属性 | 默认 `uid` |
| 启用属性映射 | 勾选，映射如 `{"uid":"username"}` |
| 创建用户（如果不存在） | 勾选则开启 JIT 自动建号 |

#### B-3. 4A 侧配置

1. 按 §5.1 纳管 JumpServer（`app_type=bastion`）。
2. 将 4A 中「运维组」用户与 IdP/JumpServer 账号对齐（用户名字段一致，如 `username`）。
3. 在 4A 门户提供跳转入口（见 §6.5）。

### 6.4 方案 A（4A 作为 IdP）：需开发规范

若要求「用户只在 4A 登录，JumpServer 认 4A」，需在 4A 后端新增如下接口（建议前缀 `/api/v1/sso`）。

#### A-1. OIDC Provider 接口

| 方法 | 路径 | 作用 | 关键返回 |
|------|------|------|----------|
| GET | `/.well-known/openid-configuration` | Discovery | `issuer`、各端点地址、`scopes_supported`、`id_token_signing_alg_values_supported=["RS256"]` |
| GET | `/api/v1/sso/oidc/authorize` | 授权端点 | 校验 4A 会话；未登录先跳 4A 登录；成功后 302 回 `redirect_uri?code=...&state=...` |
| POST | `/api/v1/sso/oidc/token` | 换取 token | `{access_token, id_token, token_type, expires_in, refresh_token?}` |
| GET | `/api/v1/sso/oidc/userinfo` | 用户信息 | `{sub, preferred_username, name, email, groups}` |
| GET | `/api/v1/sso/oidc/jwks` | 公钥 | JWKS，供 JumpServer 验签 |

**`id_token` / `userinfo` 声明映射（务必对齐 JumpServer 用户名）**：

| OIDC 声明 | 取 4A 字段 | 说明 |
|-----------|-----------|------|
| `sub` | 用户 ID（稳定不变） | 唯一标识 |
| `preferred_username` | `users.username` | **JumpServer 建号/匹配的主键** |
| `name` | `users.name` | 显示名 |
| `email` | `users.email` | 可选 |
| `groups` | 用户所属组 | 可选，用于 JumpServer 授权 |

**安全要点**：
- 严格校验 `redirect_uri` 白名单（与 JumpServer 登记回调一致）。
- `code` 一次性、短时效（≤ 60s）；`state` 必须回显校验（防 CSRF）。
- ID Token 用 RS256 签名，`iss` / `aud` / `exp` 校验；提供 `/jwks`。
- 建议同时实现 `POST /api/v1/sso/logout` 与 OIDC `end_session_endpoint`，支持单点登出。

#### A-2. CAS Provider 接口（若 JumpServer 用 CAS）

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/api/v1/sso/cas/login?service=<url>` | 未登录跳 4A 登录；已登录则 302 `service?ticket=ST-...` |
| GET | `/api/v1/sso/cas/serviceValidate?service=&ticket=` | 校验 ST，返回 `<cas:authenticationSuccess><cas:user>username</cas:user>...` |
| GET | `/api/v1/sso/cas/logout?service=` | 单点登出 |

然后按 §6.3 B-2 在 JumpServer 侧填 `服务端地址 = https://<4a>/api/v1/sso/cas`，`版本 = 3`。

#### A-3. 落地顺序建议

1. 先做 OIDC Discovery + authorize + token + userinfo + jwks（最小闭环）。
2. JumpServer 侧按 §6.3 B-1 填写 4A 的端点，用测试账号联调。
3. 补齐登出、`groups` 映射、错误审计（`category=auth`，`action=sso_login` / `sso_login_failed`）。

### 6.5 SSO 跳转入口（现有接口，建议前端接入）

- `GET /api/v1/apps/launchable` 返回当前用户可访问的应用列表。
- `POST /api/v1/apps/{id}/launch` 返回 `{app_id, app_name, protocol, redirect_url, ticket}`。
- **现状**：前端 `appApi.launch` 已定义（`frontend/src/api/endpoints.ts`），但**门户尚未接入调用**；且后端返回字段为 `redirect_url`，而前端类型标注为 `url`，两者不一致，接入前需对齐。
- **接入前必须**：确认 JumpServer 能被真实免登（即 §6.3 或 §6.4 已生效），否则该弹窗只是「打开登录页」。

**前端接入示例（示意）**：

```ts
const res = await api.post<{ redirect_url: string }>(`/apps/${id}/launch`)
window.open(res.redirect_url, '_blank', 'noopener')
```

---

## 7. 对接方式三：账号 / 组织同步（🚧）

### 7.1 目标

- 用户在 4A 停用/删除后，JumpServer 侧同步失效（**离场**能力，4A 合规关键项）。
- 4A 的组织 / 组 → JumpServer 的组织 / 用户组，用于授权。

### 7.2 方式对比

| 方式 | 方向 | 说明 | 适用 |
|------|------|------|------|
| LDAP / AD | JumpServer → 目录服务 | JumpServer「认证设置 → LDAP」直接读取统一目录 | 已有 AD/LDAP（4A 目前**不含**目录服务端，需外部提供） |
| REST API 同步 | 4A → JumpServer | 4A 通过 JumpServer API 建号/停用/分组 | 4A 作为主账号源 |

### 7.3 JumpServer API 认证

**接口文档**：`http://<jumpserver>/api/docs`

| 认证方式 | 说明 |
|----------|------|
| Token | `POST /api/v1/authentication/auth/`，body `{"username","password"}` → 返回 `token`，请求头 `Authorization: Bearer <token>`，有有效期 |
| Private Token | 永久 token（管理员在后台为用户生成），适合服务集成 |
| Access Key | 对 HTTP Header 签名（KeyID + SecretID） |

**获取 Token 示例**：

```bash
TOKEN=$(curl -s -X POST "https://jumpserver.example.com/api/v1/authentication/auth/" \
  -H "Content-Type: application/json" \
  -d '{"username":"api-bot","password":"********"}' | jq -r .token)
```

**通用请求头**：

```http
Authorization: Bearer <TOKEN>
Accept: application/json
X-JMS-ORG: 00000000-0000-0000-0000-000000000002   # 多组织时必填
```

### 7.4 同步接口（示例，端点以实际版本 `/api/docs` 为准）

| 用途 | 方法与路径（示例） |
|------|--------------------|
| 用户列表 / 创建 / 更新 / 停用 | `/api/v1/users/users/` |
| 用户组 | `/api/v1/users/groups/` |
| 资产（主机/设备） | `/api/v1/assets/assets/` |
| 资产授权 | `/api/v1/perms/asset-permissions/` |
| 命令过滤 / 授权规则 | `/api/v1/perms/` 下相关端点 |

### 7.5 字段映射建议

| 4A 字段 | JumpServer 字段 | 说明 |
|---------|-----------------|------|
| `user.username` | `username` | **匹配主键**，务必一致 |
| `user.name` | `name` | 显示名 |
| `user.email` | `email` | 可选 |
| `user.status`（active/disabled） | `is_active` | 停用即同步 `is_active=false` |
| `group.name` | 用户组 `name` | 组织/组映射 |
| 设备 `name` / `url` | 资产 `name` / `address` | 资产对齐 |

### 7.6 同步策略

- **推荐**：4A → JumpServer 单向为主（4A 为账号权威源），JumpServer 侧开启「JIT 建号」作为补充。
- **频率**：定时全量（如每日）+ 变更触发（4A 用户停用/删除时即时调用 JumpServer API 停用）。
- **幂等**：以 `username` 为唯一键 upsert；失败重试并落 4A 审计（`category=account`，`action=user_sync` / `user_sync_failed`）。

---

## 8. 对接方式四：审计数据对接

### 8.1 平台侧审计（✅ 现有）

- 4A 记录：登录/登出/MFA、账号管理、授权变更、设备连接、密码托管操作。
- 连接审计额外关联**会话日志**（终端操作回放文本）。
- 查询接口：`GET /api/v1/audits`、`GET /api/v1/audits/stats?days=7`、`GET /api/v1/audits/{id}/log-content`。

### 8.2 拉取 JumpServer 审计（🚧 增量开发）

JumpServer 侧有登录日志、操作日志、会话记录、命令记录等。若要汇总到 4A：

| 步骤 | 做法 |
|------|------|
| 1 | 在 4A 新增「外部审计采集器」，用 §7.3 的 Token 轮询 JumpServer 审计端点（如 `/api/v1/audits/login-logs/`、`/api/v1/audits/operate-logs/`，会话/命令记录在 `/api/v1/terminal/...` 下，具体以 `/api/docs` 为准） |
| 2 | 归一化为 4A `audit_logs`：`category` 建议新增 `bastion`（或复用 `connection`），`action` 用 `jms_session` / `jms_command` / `jms_login` |
| 3 | 用外部唯一键（JumpServer 记录 ID）做幂等去重，避免重复入库 |
| 4 | 会话录屏文件按需转存（`AUDIT_LOG_DIR`），并在 `detail` 中记录来源与跳转链接 |

### 8.3 反向推送（可选）

- 若企业已有 SIEM / 日志中心，可让 4A 与 JumpServer **各自**向 SIEM 推送，比「两系统互推」更简单、耦合更低。
- 4A 侧可基于审计表做增量导出（REST 或 syslog），JumpServer 侧用其原生日志输出能力。

### 8.4 审计一致性要点

- 同一用户同一次运维动作，在 4A 与 JumpServer 各留一份**互补**记录：4A 记「入口/授权/凭证解析」，JumpServer 记「会话内命令级操作」。
- 建议以 `(username, 时间窗, 目标资产)` 作为关联键，便于跨系统追溯。

---

## 9. 联调与验收清单

### 9.1 资产纳管

- [ ] 4A 中可见 `堡垒机 JumpServer` 纳管对象（`app_type=bastion`）。
- [ ] 「检测」返回 `online`（或预期的 `unreachable` 且原因符合预期）。
- [ ] 对未授权用户，「连接」不可用或返回 `403 无权访问该设备`。
- [ ] 点击「连接」并用 Chrome/MobaXterm/WinSCP 成功拉起工具。
- [ ] 助手回传会话日志后，`GET /api/v1/audits/{id}/log-content` 可读取。
- [ ] 一次连接审计表**只有一条** `connection` 记录，`action` 为 `<协议>连接`。

### 9.2 SSO（按所选方案）

- [ ] 从 IdP 门户点 JumpServer 可免登进入（方案 B）。
- [ ] 从 JumpServer 登录页可跳 IdP 登录（SP 发起）。
- [ ] 注销 4A / IdP 后，JumpServer 会话按策略失效。
- [ ] 首次登录可 JIT 建号，且 `username` 与 4A 一致。

### 9.3 账号同步

- [ ] 4A 新建用户后，JumpServer 定时同步可见。
- [ ] 4A 停用用户后，JumpServer 侧同步 `is_active=false`，无法登录。
- [ ] 同步失败有审计且可重试。

### 9.4 审计汇聚

- [ ] JumpServer 会话/命令记录可归一化入 4A 审计表。
- [ ] 幂等去重生效（重复采集不产生重复行）。
- [ ] 可用用户名 / 时间 / 资产跨系统关联追溯。

---

## 10. 常见问题（FAQ）

**Q1：点了「启动应用」打开了 JumpServer，但还要再登录一次？**
A：正常。当前 `launch` 是简化跳转，JumpServer 不认 ticket。要免登请完成 §6 的 SSO 对接。

**Q2：`/apps/{id}/launch` 返回 `redirect_url`，前端为什么拿不到 `url`？**
A：后端返回 `redirect_url`，前端 `endpoints.ts` 类型标注为 `url`，字段不一致，接入前需对齐（见 §6.5）。

**Q3：纳管后「检测」显示 `unreachable`？**
A：`url` 为网段或协议无固定端口时会如此。改成单点 `host:port` 后重试。

**Q4：JumpServer OIDC/SAML 配置项在社区版找不到？**
A：OIDC / SAML2 自 v3 起为 X-Pack 企业版功能；CAS 一般社区版可用。购买版或改用 CAS，请以官方版本说明为准。

**Q5：用哪个账号调 JumpServer API？**
A：建专用服务账号（如 `api-bot`），优先用 Private Token；避免复用管理员长期密码。

**Q6：会话日志看不到内容？**
A：确认连接助手版本（连接审计的 `detail.客户端版本`），并确认工具本身产生了会话日志（如 MobaXterm 部分协议需开启日志）。详见「连接工具」页下载最新助手。

---

## 11. 附录

### 11.1 平台侧相关接口速查

| 方法与路径 | 说明 |
|-----------|------|
| `POST /api/v1/apps` | 新增纳管对象 |
| `GET /api/v1/apps` | 设备列表（`q` / `app_type` 过滤） |
| `POST /api/v1/apps/{id}/check` | 连通性检测 |
| `POST /api/v1/apps/{id}/connect` | 签发连接票据（写连接审计） |
| `POST /api/v1/apps/connect/resolve` | 助手解析票据（返回凭证明文给本地助手） |
| `POST /api/v1/apps/connect/upload-log` | 助手回传会话日志 |
| `POST /api/v1/apps/{id}/launch` | SSO 跳转（简化） |
| `GET /api/v1/apps/launchable` | 当前用户可访问应用 |
| `GET/POST /api/v1/apps/{id}/users`、`DELETE /api/v1/apps/{id}/users/{user_id}` | 设备授权用户 |
| `GET /api/v1/audits`、`/api/v1/audits/stats`、`/api/v1/audits/{id}/log-content` | 审计查询与日志正文 |

> 权威定义以 [`docs/api-contract.md`](api-contract.md) 为准。

### 11.2 JumpServer 侧信息

- 官方文档：<https://docs.jumpserver.org>
- OIDC 对接：<https://www.jumpserver.com/docs/authentication/oidc>
- API 文档：`http://<jumpserver>/api/docs`
- API 认证说明：Session / Token / Private Token / Access Key 四种方式

### 11.3 安全基线

1. JumpServer 升级到安全版本：**V3 ≥ v3.10.23 LTS、V4 ≥ v4.10.19 LTS**（针对 JS-2026.09.09 Access Key 越权问题）。
2. 4A 与 JumpServer 之间走 HTTPS，校验证书。
3. JumpServer API 使用专用最小权限账号 + Private Token，凭证入 4A 密码托管并定期轮换。
4. 生产环境修改 4A 默认管理员口令与 `SECRET_KEY` / 加密密钥（见 [`docs/deployment.md`](deployment.md)）。
5. SSO 严格实现 `state`、`nonce`、`redirect_uri` 白名单与 ID Token 验签。

---

## 12. 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-10-14 | 首版：资产纳管（现有）、SSO（方案 A/B + 接口规范）、账号同步、审计汇聚 |
