# 4A 平台 API 契约（v1）

所有接口前缀：`/api/v1`。认证方式：`Authorization: Bearer <access_token>`。
统一错误体：`{"detail": "..."}`（FastAPI 默认）。分页响应：`{items, total, page, page_size}`。

## 权限码（用于前端菜单/按钮控制）

```
dashboard:read
user:read user:write user:delete user:reset_password
group:read group:write group:delete
org:read org:write org:delete
application:read application:write application:delete
role:read role:write role:delete
permission:read
policy:read policy:write policy:delete
audit:read
secret:read secret:reveal secret:write secret:delete secret:rotate
```

## 认证 /auth

| 方法 | 路径 | 权限 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | /auth/login | 公开 | `{username,password,otp_code?}` | `LoginResult` |
| POST | /auth/mfa/verify | 公开 | `{mfa_token,otp_code}` | `LoginResult` |
| POST | /auth/refresh | 公开 | `{refresh_token}` | `TokenPair` |
| POST | /auth/logout | 登录 | `{refresh_token?}` | `{message}` |
| GET | /auth/me | 登录 | - | `MeOut` |
| POST | /auth/change-password | 登录 | `{old_password,new_password}` | `{message}` |
| POST | /auth/mfa/setup | 登录 | - | `{secret,otpauth_uri}` |
| POST | /auth/mfa/enable | 登录 | `{code}` | `{message}` |
| POST | /auth/mfa/disable | 登录 | `{code}` | `{message}` |

`LoginResult`: `{access_token?, refresh_token?, token_type, expires_in, mfa_required, mfa_token?, user?}`
`MeOut` = UserOut + `{permissions: string[], roles: RoleBrief[], groups: GroupBrief[], org_name?}`

## 账号 /users /groups /orgs

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /users?page&page_size&q&status&org_id | user:read | 分页 `Page<UserOut>` |
| POST | /users | user:write | 创建，返回 `UserDetailOut` |
| GET | /users/{id} | user:read | `UserDetailOut` |
| PUT | /users/{id} | user:write | `UserUpdate` → `UserDetailOut` |
| DELETE | /users/{id} | user:delete | 禁止删除自己 |
| POST | /users/{id}/reset-password | user:reset_password | `{new_password?}`（空则随机生成并返回 message 含临时密码） |
| POST | /users/{id}/roles | user:write | `{role_ids: int[]}` |
| POST | /users/{id}/groups | user:write | `{group_ids: int[]}` |
| POST | /users/{id}/unlock | user:write | 解除锁定 |

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /groups | group:read | `GroupOut[]` |
| POST | /groups | group:write | `GroupCreate` |
| PUT | /groups/{id} | group:write | `GroupUpdate` |
| DELETE | /groups/{id} | group:delete | |
| GET | /groups/{id}/members | group:read | `UserOut[]` |
| POST | /groups/{id}/members | group:write | `{user_ids: int[]}` |
| DELETE | /groups/{id}/members/{user_id} | group:write | |

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /orgs | org:read | `OrgOut[]` |
| GET | /orgs/tree | org:read | `OrgTree[]` |
| POST | /orgs | org:write | `OrgCreate` |
| PUT | /orgs/{id} | org:write | `OrgUpdate` |
| DELETE | /orgs/{id} | org:delete | 有子节点/用户时拒绝 |

## 授权 /apps /roles /permissions /policies

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /apps?page&page_size&q&app_type | application:read | `Page<AppOut>` |
| POST | /apps | application:write | `AppCreate` |
| GET | /apps/{id} | application:read | `AppOut` |
| PUT | /apps/{id} | application:write | `AppUpdate` |
| DELETE | /apps/{id} | application:delete | |
| GET | /apps/launchable | 登录 | 当前用户可访问的 `AppOut[]` |
| POST | /apps/{id}/launch | 登录 | 生成 SSO ticket，返回 `AppLaunchOut` |
| GET | /apps/{id}/users | application:read | 已授权用户 `UserOut[]` |
| POST | /apps/{id}/users | application:write | `{user_ids: int[]}` 覆盖式 |
| DELETE | /apps/{id}/users/{user_id} | application:write | |

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /roles | role:read | `RoleOut[]` |
| POST | /roles | role:write | `RoleCreate` |
| GET | /roles/{id} | role:read | `RoleDetailOut` |
| PUT | /roles/{id} | role:write | `RoleUpdate` |
| DELETE | /roles/{id} | role:delete | 内置角色禁止删除 |
| POST | /roles/{id}/permissions | role:write | `{permission_ids: int[]}` |

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /permissions | permission:read | `PermissionOut[]`（可按 resource 分组返回） |

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /policies?page&page_size&q | policy:read | `Page<PolicyOut>` |
| POST | /policies | policy:write | `PolicyCreate` |
| PUT | /policies/{id} | policy:write | `PolicyUpdate` |
| DELETE | /policies/{id} | policy:delete | |
| POST | /policies/evaluate | policy:read | `PolicyEvaluateRequest` → `PolicyEvaluateResult` |

## 审计 /audits

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /audits?page&page_size&category&result&actor_username&action&start&end | audit:read | `Page<AuditOut>` |
| GET | /audits/stats?days=7 | audit:read | `AuditStats` |

## 密码托管 /secrets /rotations

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /secrets?page&page_size&q&category | secret:read | `Page<SecretOut>` |
| POST | /secrets | secret:write | `SecretCreate`（含 data） |
| GET | /secrets/{id} | secret:read | `SecretOut` |
| PUT | /secrets/{id} | secret:write | `SecretUpdate` |
| DELETE | /secrets/{id} | secret:delete | |
| GET | /secrets/{id}/value?version&reveal | secret:read(+reveal) | `SecretValueOut`（无 reveal 权限时 data 为脱敏值） |
| POST | /secrets/{id}/value | secret:write | `{data,comment?}` 写入新版本 |
| GET | /secrets/{id}/versions | secret:read | `SecretVersionOut[]` |
| POST | /secrets/{id}/rotate | secret:rotate | `RotateResult` |

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /rotations/due | secret:read | 到期未轮换的 `SecretOut[]` |
| POST | /rotations/run | secret:rotate | 立即扫描并轮换，返回 `{processed, succeeded, failed, results[]}` |

## 仪表盘 /dashboard

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /dashboard/stats | dashboard:read | `DashboardStats` |

## 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /healthz | 存活探针 |
| GET | /readyz | 就绪探针 |
| GET | /docs | Swagger UI |

## 审计埋点要求（所有写操作必须落审计）

- 认证：`auth` / `login`、`login_failed`、`logout`、`mfa_*`
- 账号：`account` / `user_create`、`user_update`、`user_delete`、`user_reset_password`、`role_assign`…
- 授权：`authz` / `role_*`、`policy_*`、`app_*`
- 密码托管：`vault` / `secret_create`、`secret_update`、`secret_reveal`、`secret_rotate`、`secret_delete`
- 失败事件 result=`failure`
