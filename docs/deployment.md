# 4A 平台部署运维手册

面向小团队（<10 人）的极简运维方案：单机部署 = FastAPI(systemd) + Nginx 反代 + SQLite/PostgreSQL。
无需中间件集群，默认无外部依赖，可长期维护。

## 1. 环境要求

| 组件 | 版本要求 |
|------|----------|
| 操作系统 | Linux（systemd + Nginx 可用即可，如 CentOS 7+ / Ubuntu 20.04+） |
| Python | 3.11+ |
| Node.js | 18+（仅构建前端时使用，生产机可不用装） |
| 磁盘 | 建议预留 ≥ 20GB（含数据库与备份） |

## 2. 开发环境部署

```bash
# 后端
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn app.main:app --reload --port 8000
# Swagger: http://127.0.0.1:8000/docs

# 前端（另开终端）
cd frontend
npm install
npm run dev   # http://127.0.0.1:5173
```

开发时前端通过 Vite 代理把 `/api` 转发到 `127.0.0.1:8000`（见 `frontend/vite.config.ts`），
无需配置 CORS 之外的额外内容。首次启动自动建表 + 植入种子数据（权限/角色/示例数据/管理员）。

> 默认管理员：`admin` / `Admin@12345` —— **生产环境务必通过环境变量改掉**（见第 4 节）。

## 3. 生产部署（systemd + Nginx）

### 3.1 目录规划

```text
/opt/4a-platform/
├── backend/            # 后端代码 + .venv + data/（数据库）
├── frontend/dist/      # 前端构建产物
├── deploy/             # 本仓库提供的 systemd / nginx 模板
└── .env                # 后端环境变量（权限 600）
```

### 3.2 创建运行用户并部署代码

```bash
sudo useradd -r -s /usr/sbin/nologin 4a
sudo mkdir -p /opt/4a-platform
sudo chown 4a:4a /opt/4a-platform

# 以 4a 用户部署
sudo -u 4a bash
cd /opt/4a-platform
git clone <your-repo> .
# 后端依赖
cd backend && python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
exit
```

### 3.3 配置环境变量

创建 `/opt/4a-platform/.env`（内容见第 4 节），权限收紧：

```bash
sudo chmod 600 /opt/4a-platform/.env
```

### 3.4 安装 systemd 单元

请先核对 `deploy/systemd/4a-backend.service` 中的路径/用户，然后：

```bash
sudo cp deploy/systemd/4a-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now 4a-backend
sudo systemctl status 4a-backend
```

单元要点：`User=4a`、`Restart=always`、`ProtectSystem=full`、仅数据目录可写
（`ReadWritePaths=/opt/4a-platform/backend/data`）。

### 3.5 构建前端并配置 Nginx

```bash
# 在构建机上（或本机安装 node）
cd frontend && npm install && npm run build
# 产物在 frontend/dist/，拷到 /opt/4a-platform/frontend/dist/
sudo cp -r frontend/dist /opt/4a-platform/frontend/
```

调整 `deploy/nginx/4a.conf` 中的 `server_name`、证书路径、`root`，然后：

```bash
sudo cp deploy/nginx/4a.conf /etc/nginx/conf.d/4a.conf
sudo nginx -t && sudo systemctl reload nginx
```

### 3.6 验证

```bash
curl -s https://iam.corp.example.com/healthz   # {"status":"ok"}
curl -s https://iam.corp.example.com/readyz   # {"status":"ready"}
curl -s -X POST https://iam.corp.example.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<新密码>"}'
```

## 4. 环境变量（.env 全量说明）

| 变量 | 默认值 | 生产建议 |
|------|--------|----------|
| `ENVIRONMENT` | `development` | **`production`**（触发主密钥强校验、禁用调试） |
| `SECRET_KEY` | `dev-insecure-secret-change-me` | **必改**：`openssl rand -hex 32` 生成 |
| `DATABASE_URL` | `sqlite:///./data/4a.db` | 默认即可；可切 PostgreSQL：`postgresql://user:pass@host:5432/4a` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | 默认 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | 默认 |
| `PASSWORD_MIN_LENGTH` | `12` | 默认（合规基线） |
| `VAULT_MASTER_KEY` | 空 | **必配**：`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `VAULT_KEY_FAIL_MODE` | `fail` | 默认；生产下缺主密钥直接拒绝启动 |
| `MAX_FAILED_LOGINS` | `5` | 默认 |
| `LOCKOUT_MINUTES` | `15` | 默认 |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 改为真实前端域名：`https://iam.corp.example.com` |
| `ROTATION_SCHEDULER_ENABLED` | `true` | 默认开启密码轮换扫描 |
| `ROTATION_CHECK_CRON` | `0 2 * * *` | 每天 02:00 UTC 扫描 |
| `BOOTSTRAP_ADMIN_USERNAME` | `admin` | 生产首启前改掉 |
| `BOOTSTRAP_ADMIN_PASSWORD` | `Admin@12345` | **生产首启前必改**（仅首次建库生效） |
| `BOOTSTRAP_ADMIN_EMAIL` | `admin@corp.example.com` | 改真实邮箱 |

示例 `.env`：

```bash
ENVIRONMENT=production
SECRET_KEY=<openssl rand -hex 32>
VAULT_MASTER_KEY=<Fernet 主密钥>
CORS_ORIGINS=https://iam.corp.example.com
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=<强密码，符合密码策略>
BOOTSTRAP_ADMIN_EMAIL=admin@corp.example.com
```

## 5. 安全管理

1. **密钥管理**：`SECRET_KEY` 与 `VAULT_MASTER_KEY` 分开存放，`.env` 权限 600；
   有条件可接入 KMS/密钥文件，主密钥不落代码仓库。
2. **密码策略**：默认 ≥12 位含大小写/数字/特殊字符，登录防爆破 5 次锁定 15 分钟，均无需额外配置。
3. **HTTPS**：Nginx 强制 TLS（模板已含 http2），证书建议 Let's Encrypt 自动续期。
4. **最小权限**：内置角色只读/审计分离；`secret:reveal` 仅授予 `secret-admin` 一类角色；
   前端菜单按权限码动态渲染，后端路由级鉴权兜底。
5. **审计**：所有写操作自动落 `audit_logs`，定期导出审计报表（`GET /api/v1/audits` 支持过滤）。

## 6. 备份与恢复

### 6.1 SQLite（默认）

```bash
# 备份（在线一致性：SQLite 官方 .backup 命令）
sqlite3 /opt/4a-platform/backend/data/4a.db ".backup '/backup/4a-$(date +%F).db'"
# 或直接复制文件（建议先停服 1 秒）：
sudo systemctl stop 4a-backend
cp /opt/4a-platform/backend/data/4a.db /backup/4a-$(date +%F).db
sudo systemctl start 4a-backend
```

> 注意：`VAULT_MASTER_KEY` / `SECRET_KEY` 必须与数据库一起备份（丢失主密钥 = 托管密码无法解密），
> 且密钥文件本身要单独加密保存。

### 6.2 恢复

```bash
sudo systemctl stop 4a-backend
cp /backup/4a-<date>.db /opt/4a-platform/backend/data/4a.db
sudo systemctl start 4a-backend   # 启动时自动幂等执行 seed，补齐缺失的种子数据
```

### 6.3 切换 PostgreSQL（可选）

```bash
# 1) 预装依赖（psycopg2 已在 requirements.txt）
# 2) 建库授权
sudo -u postgres psql -c "CREATE USER 4a WITH PASSWORD '<强密码>';"
sudo -u postgres psql -c "CREATE DATABASE 4a OWNER 4a;"
# 3) 修改 .env 的 DATABASE_URL，重启服务即可（表结构自动创建 + 种子）
sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql://4a:<强密码>@127.0.0.1:5432/4a|' /opt/4a-platform/.env
sudo systemctl restart 4a-backend
```

> SQLite → PG 数据迁移：可用 `sqlite3 .dump` + 脚本转换，或简单起见重新建库由种子初始化后再录入。

## 7. 健康检查与监控

- `/healthz`：存活探针（进程级）。
- `/readyz`：就绪探针（数据库可用性）。

最小化监控建议（避免引入重依赖）：

```bash
# systemd 自愈已内置（Restart=always）；再加一个 cron 探活即可
*/5 * * * * curl -fsS https://iam.corp.example.com/healthz || systemctl restart 4a-backend
```

日志查看：`sudo journalctl -u 4a-backend -f`；运维告警可选接入钉钉/企业微信 Webhook。

## 8. 日常运维速查

| 操作 | 命令 |
|------|------|
| 启动/停止/重启 | `sudo systemctl {start,stop,restart} 4a-backend` |
| 查看状态 | `sudo systemctl status 4a-backend` |
| 实时日志 | `sudo journalctl -u 4a-backend -f` |
| 重载 Nginx | `sudo nginx -t && sudo systemctl reload nginx` |
| 手动轮换扫描 | `curl -X POST https://iam.corp.example.com/api/v1/rotations/run -H "Authorization: Bearer <token>"` |
| 运行测试 | `cd backend && ./.venv/bin/pytest -q` |
| 构建前端 | `cd frontend && npm run build` |
| 升级版本 | 备份 → 拉代码 → `pip install -r requirements.txt` → `npm run build` → `systemctl restart 4a-backend` → 冒烟（登录/列表/密钥读写） |

## 9. 扩容方向（当前规模无需）

当前约 1000 台设备的纳管规模下单机完全够用。若未来规模增长（数万账号、高并发登录）：
API 层多副本 + Nginx upstream 负载均衡、数据库切换 PostgreSQL 并做主从、会话令牌短时效化 +
刷新令牌落 Redis 共享。以上均为配置级改动，业务代码无需重构。