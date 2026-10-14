# 4A 平台部署运维手册

面向小团队（<10 人）的极简运维方案：单机部署 = 后端(FastAPI) + 前端(React 静态产物)，
默认 SQLite、零外部依赖，可长期维护。

支持 **三种部署方式**，且都提供 **一键部署 / 一键更新** 脚本：

| 方式 | 适用场景 | 说明 |
|------|----------|------|
| **Docker Compose**（推荐） | 已装 Docker 的服务器 | 单容器，前端 + 后端同端口，无需额外 Nginx |
| **Docker** | 只用原生 `docker run` 的场景 | 手动 `docker build` + `docker run` |
| **systemd + Nginx** | 裸机 / 无 Docker 环境 | Python 虚拟环境 + systemd 托管 + Nginx 反代 |

三种方式的前端与 API 均**同源同端口**（后端直接托管前端 SPA，见 `backend/app/main.py` 的 `SERVE_FRONTEND`），
因此无需配置 CORS。

---

## 0. 一键部署脚本 `deploy.sh`

仓库根目录的 `deploy.sh` 同时支持三种方式与全部日常操作，**一条命令即可部署或更新**。

```bash
# 查看帮助
./deploy.sh help

# 部署（三选一）
./deploy.sh install --mode compose                 # Docker Compose（推荐）
./deploy.sh install --mode docker  --port 8000     # 原生 Docker
sudo ./deploy.sh install --mode systemd            # systemd + Nginx
```

### 支持的动作

| 动作 | 说明 |
|------|------|
| `install` | 首次部署（构建 + 启动）。`install` 时必须用 `--mode` 指定方式 |
| `update` | **一键更新**：拉取最新代码 → 重新构建 → 滚动重启（数据保留） |
| `start` / `stop` / `restart` | 启动 / 停止 / 重启服务 |
| `status` | 查看运行状态 |
| `logs` | 实时查看日志 |
| `uninstall` | 停止并移除服务（数据默认保留） |

> 安装后脚本会把部署方式与参数写入状态文件（root 为 `/etc/lycloud4a/deploy.conf`，
> 普通用户为 `~/.config/lycloud4a/deploy.conf`）。之后执行 `update` / `logs` 等**无需再指定 `--mode`**。

### 常用选项

| 选项 | 默认 | 说明 |
|------|------|------|
| `--mode <m>` | — | `compose` / `docker` / `systemd`（`install` 必填） |
| `--port <p>` | `8000` | 对外端口 |
| `--dir <path>` | `/opt/4a-platform` | systemd 模式的安装目录 |
| `--domain <d>` | — | systemd+Nginx 的 `server_name` |
| `--tls-cert` / `--tls-key` | — | 提供则启用 HTTPS，否则仅 HTTP |
| `--repo <url>` | GitHub HTTPS | 服务器无 SSH key 时用 HTTPS；已配 SSH 可用 `git@github.com:luolu1/lycloud4A.git` |
| `--branch <b>` | `main` | git 分支 |
| `--no-nginx` | — | systemd 模式不配置 Nginx（仅启动后端） |
| `-y, --yes` | — | 跳过确认 |

脚本会自动从 `.env.example` 生成 `.env` 并写入随机的 `SECRET_KEY` 与 `VAULT_MASTER_KEY`，
**请务必备份生成的 `VAULT_MASTER_KEY`**（丢失后托管密码无法解密）。

### 一键更新（三种方式统一）

```bash
./deploy.sh update          # 自动识别已安装方式，拉代码 → 重建 → 重启
```

---

## 1. 环境要求

| 组件 | Docker 方式 | systemd 方式 |
|------|-------------|--------------|
| 操作系统 | 任意可运行 Docker 的 Linux | Linux，需 systemd（CentOS 7+ / Ubuntu 20.04+ 等） |
| Docker | 20.10+（含 `docker compose` 插件） | 不需要 |
| Python | 不需要（镜像内置） | 3.11+ |
| Node.js | 不需要（镜像内构建） | 18+（构建前端用） |
| Nginx | 不需要 | 可用即可（可选） |
| 磁盘 | ≥ 20GB（含数据库与备份） | ≥ 20GB |

Docker 安装（如需）：`curl -fsSL https://get.docker.com | sh`。

---

## 2. 方式一：Docker Compose（推荐）

单容器：镜像内已构建前端产物，后端通过 `SERVE_FRONTEND=true` 直接托管 SPA，
`/api` 与前端同端口提供，无需额外 Nginx。

### 2.1 一键部署

```bash
git clone https://github.com/luolu1/lycloud4A.git
cd lycloud4A
./deploy.sh install --mode compose
```

脚本会：同步代码 → 生成 `.env`（随机密钥）→ `docker compose up -d --build`。

### 2.2 等价的手动命令

```bash
cp .env.example .env         # 然后修改 SECRET_KEY / VAULT_MASTER_KEY / 管理员密码
docker compose up -d --build
docker compose ps
docker compose logs -f
```

关键文件：

- `Dockerfile`：多阶段构建（Node 构建前端 → Python 运行时 + 前端产物）
- `docker-compose.yml`：单服务 `app`，数据卷 `lycloud4a-data` 挂载到 `/app/backend/data`
- `.env`：环境变量（端口 `APP_PORT`、密钥、管理员等）

数据持久化：SQLite 数据库与会话日志都在数据卷 `lycloud4a-data`，删除容器不影响数据。

### 2.3 一键更新

```bash
./deploy.sh update            # = git pull → docker compose up -d --build
```

或手动：`git pull && docker compose up -d --build`。

---

## 3. 方式二：Docker（原生）

不使用 Compose，直接用 `docker build` + `docker run`，脚本已封装好参数。

### 3.1 一键部署

```bash
git clone https://github.com/luolu1/lycloud4A.git
cd lycloud4A
./deploy.sh install --mode docker --port 8000
```

脚本会构建镜像 `lycloud4a:latest`，并以 `--restart unless-stopped` 启动名为 `lycloud4a` 的容器，
数据卷 `lycloud4a-data` 挂载到 `/app/backend/data`。

### 3.2 等价的手动命令

```bash
docker build -t lycloud4a:latest .
docker run -d --name lycloud4a --restart unless-stopped \
  --env-file .env \
  -e ENVIRONMENT=production -e SERVE_FRONTEND=true \
  -e FRONTEND_DIST_DIR=/app/frontend/dist \
  -p 8000:8000 \
  -v lycloud4a-data:/app/backend/data \
  lycloud4a:latest
```

### 3.3 一键更新

```bash
./deploy.sh update            # = git pull → docker build → 替换容器（数据卷保留）
```

---

## 4. 方式三：systemd + Nginx（裸机）

### 4.1 一键部署

```bash
git clone https://github.com/luolu1/lycloud4A.git
cd lycloud4A
sudo ./deploy.sh install --mode systemd --domain iam.corp.example.com
```

脚本会：创建 `4a` 运行用户 → 克隆/更新代码到 `/opt/4a-platform` → 建虚拟环境装依赖 →
`npm ci && npm run build` 构建前端 → 生成 `.env` → 安装 systemd 单元 `lycloud4a.service` →
生成 Nginx 配置 `/etc/nginx/conf.d/lycloud4a.conf`（HTTP；提供 `--tls-cert/--tls-key` 则启用 HTTPS）。

常用变体：

```bash
# 使用自定义安装目录与端口
sudo ./deploy.sh install --mode systemd --dir /srv/4a --port 8080

# 启用 HTTPS
sudo ./deploy.sh install --mode systemd --domain iam.corp.example.com \
  --tls-cert /etc/nginx/certs/iam.crt --tls-key /etc/nginx/certs/iam.key

# 不配置 Nginx（仅由后端提供 127.0.0.1:8000）
sudo ./deploy.sh install --mode systemd --no-nginx
```

### 4.2 目录规划

```text
/opt/4a-platform/
├── backend/            # 后端代码 + .venv + data/（SQLite 与审计日志）
├── frontend/dist/      # 前端构建产物（Nginx 静态托管；后端也可直接托底）
├── deploy/             # 仓库自带的 systemd / nginx 参考模板
└── .env                # 环境变量（权限 600，systemd EnvironmentFile 读取）
```

### 4.3 等价的手动部署（不使用脚本时）

```bash
sudo useradd -r -s /usr/sbin/nologin 4a
sudo mkdir -p /opt/4a-platform && sudo chown 4a:4a /opt/4a-platform
sudo -u 4a git clone https://github.com/luolu1/lycloud4A.git /opt/4a-platform

cd /opt/4a-platform/backend
sudo -u 4a python3 -m venv .venv
sudo -u 4a ./.venv/bin/pip install -r requirements.txt

cd /opt/4a-platform/frontend
sudo -u 4a npm ci && sudo -u 4a npm run build

sudo cp deploy/systemd/4a-backend.service /etc/systemd/system/lycloud4a.service   # 按需改路径/端口
sudo cp deploy/nginx/4a.conf /etc/nginx/conf.d/lycloud4a.conf                     # 按需改域名/证书
sudo systemctl daemon-reload && sudo systemctl enable --now lycloud4a
sudo nginx -t && sudo systemctl reload nginx
```

### 4.4 一键更新

```bash
sudo ./deploy.sh update       # = git pull → pip install → npm build → systemctl restart → nginx reload
```

---

## 5. 验证部署

```bash
# 健康探针
curl -s http://<主机>:<端口>/healthz    # {"status":"ok"}
curl -s http://<主机>:<端口>/readyz     # {"status":"ready"}

# 登录（默认管理员 admin / Admin@12345，生产务必改）
curl -s -X POST http://<主机>:<端口>/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<密码>"}'

# 前端页面
#   http://<主机>:<端口>/          —— 打开即为登录页
```

> 默认管理员：`admin` / `Admin@12345` —— **生产环境务必通过环境变量改掉**（见第 7 节）。
> 修改仅在**首次建库**时生效；已初始化过的库需在页面中改密。

---

## 6. 开发环境部署

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

开发时前端通过 Vite 代理把 `/api` 转发到 `127.0.0.1:8000`（见 `frontend/vite.config.ts`）。
首次启动自动建表 + 植入种子数据（权限/角色/示例数据/管理员）。
后端若发现 `frontend/dist` 存在也会在 `:8000/` 直接托管 SPA（可用 `SERVE_FRONTEND=false` 关闭）。

---

## 7. 环境变量（.env 全量说明）

三种方式共用同一份 `.env`。Docker 方式由 `docker compose`/`docker run` 注入；
systemd 方式由 `EnvironmentFile=/opt/4a-platform/.env` 注入。完整示例见仓库根目录 `.env.example`。

| 变量 | 默认值 | 生产建议 |
|------|--------|----------|
| `ENVIRONMENT` | `development` | **`production`**（触发主密钥强校验、禁用调试） |
| `SECRET_KEY` | `dev-insecure-secret-change-me` | **必改**：`openssl rand -hex 32` 生成 |
| `DATABASE_URL` | `sqlite:///./data/4a.db` | 默认即可；可切 PostgreSQL：`postgresql://user:pass@host:5432/4a` |
| `VAULT_MASTER_KEY` | 空 | **必配**：`openssl rand -base64 32 \| tr '+/' '-_'`（Fernet 密钥） |
| `VAULT_KEY_FAIL_MODE` | `fail` | 默认；生产下缺主密钥直接拒绝启动 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | 默认 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | 默认 |
| `PASSWORD_MIN_LENGTH` | `12` | 默认（合规基线） |
| `MAX_FAILED_LOGINS` | `5` | 默认 |
| `LOCKOUT_MINUTES` | `15` | 默认 |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 前后端同源时无需配置；分域名时填真实前端域名 |
| `SERVE_FRONTEND` | `true` | 后端托管前端 SPA（Docker 内置前端时保持 true） |
| `FRONTEND_DIST_DIR` | 自动推导为 `frontend/dist` | 一般无需设置；Docker 镜像内为 `/app/frontend/dist` |
| `AUDIT_LOG_DIR` | `backend/data/audit_logs` | 客户端上传的终端会话归档目录 |
| `ROTATION_SCHEDULER_ENABLED` | `true` | 默认开启密码轮换扫描 |
| `ROTATION_CHECK_CRON` | `0 2 * * *` | 每天 02:00 UTC 扫描 |
| `BOOTSTRAP_ADMIN_USERNAME` | `admin` | 生产首启前改掉 |
| `BOOTSTRAP_ADMIN_PASSWORD` | `Admin@12345` | **生产首启前必改**（仅首次建库生效） |
| `BOOTSTRAP_ADMIN_EMAIL` | `admin@corp.example.com` | 改真实邮箱 |

生成强密钥：

```bash
openssl rand -hex 32                                   # SECRET_KEY
openssl rand -base64 32 | tr '+/' '-_'                  # VAULT_MASTER_KEY（Fernet）
```

---

## 8. 安全管理

1. **密钥管理**：`SECRET_KEY` 与 `VAULT_MASTER_KEY` 分开存放，`.env` 权限 600；
   有条件可接入 KMS/密钥文件，主密钥不落代码仓库。
2. **密码策略**：默认 ≥12 位含大小写/数字/特殊字符，登录防爆破 5 次锁定 15 分钟，均无需额外配置。
3. **HTTPS**：Docker 方式建议在前置 LB/网关终结 TLS；systemd 方式由 Nginx 强制 TLS（提供证书即启用）。
4. **最小权限**：内置角色只读/审计分离；`secret:reveal` 仅授予对应角色；
   前端菜单按权限码动态渲染，后端路由级鉴权兜底。
5. **审计**：所有写操作自动落 `audit_logs`，定期导出审计报表（`GET /api/v1/audits` 支持过滤）。

---

## 9. 备份与恢复

### 9.1 数据位置

| 方式 | SQLite 数据库 | 会话日志 |
|------|---------------|----------|
| Docker / Compose | 卷 `lycloud4a-data` 内 `/app/backend/data/4a.db` | 同卷 `/app/backend/data/audit_logs/` |
| systemd | `/opt/4a-platform/backend/data/4a.db` | `/opt/4a-platform/backend/data/audit_logs/` |

### 9.2 备份

```bash
# Docker：从容器/卷导出
docker run --rm -v lycloud4a-data:/data -v "$PWD:/backup" alpine \
  tar czf /backup/4a-$(date +%F).tgz -C /data .

# systemd
sqlite3 /opt/4a-platform/backend/data/4a.db ".backup '/backup/4a-$(date +%F).db'"
```

> 注意：`VAULT_MASTER_KEY` / `SECRET_KEY` 必须与数据一起备份
> （丢失主密钥 = 托管密码无法解密），且密钥要单独加密保存。

### 9.3 恢复

```bash
# Docker：停止容器 → 将备份解包回卷 → 启动
docker stop lycloud4a
docker run --rm -v lycloud4a-data:/data -v "$PWD:/backup" alpine \
  sh -c 'rm -rf /data/* && tar xzf /backup/4a-<date>.tgz -C /data'
docker start lycloud4a

# systemd
sudo systemctl stop lycloud4a
cp /backup/4a-<date>.db /opt/4a-platform/backend/data/4a.db
sudo systemctl start lycloud4a     # 启动时幂等执行 seed，补齐缺失的种子数据
```

### 9.4 切换 PostgreSQL（可选）

`docker-compose.yml` 内已提供注释形式的 `postgres` 服务，取消注释后设置 `DATABASE_URL`
（`postgresql://4a:<强密码>@postgres:5432/4a`）即可；systemd 方式按下面步骤：

```bash
sudo -u postgres psql -c "CREATE USER 4a WITH PASSWORD '<强密码>';"
sudo -u postgres psql -c "CREATE DATABASE 4a OWNER 4a;"
sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql://4a:<强密码>@127.0.0.1:5432/4a|' /opt/4a-platform/.env
sudo systemctl restart lycloud4a
```

> SQLite → PG 数据迁移：可用 `sqlite3 .dump` + 脚本转换，或重新建库由种子初始化后再录入。

---

## 10. 健康检查与监控

- `/healthz`：存活探针（进程级）。
- `/readyz`：就绪探针（数据库可用性）。

```bash
# 三种方式都可用 HTTP 探活；systemd 另有 Restart=always 自愈
*/5 * * * * curl -fsS http://127.0.0.1:8000/healthz || echo "4A unhealthy" | mail -s alert ops@corp
```

Docker 镜像内置 `HEALTHCHECK`，`docker ps` 可见健康状态。

日志：

```bash
./deploy.sh logs                              # Docker / Compose
journalctl -u lycloud4a -f                    # systemd
```

---

## 11. 日常运维速查

| 操作 | Docker / Compose | systemd |
|------|------------------|---------|
| 启动 / 停止 / 重启 | `./deploy.sh start\|stop\|restart` | `sudo ./deploy.sh start\|stop\|restart` |
| 查看状态 | `./deploy.sh status` | `./deploy.sh status` |
| 实时日志 | `./deploy.sh logs` | `sudo ./deploy.sh logs` |
| **一键更新** | `./deploy.sh update` | `sudo ./deploy.sh update` |
| 卸载 | `./deploy.sh uninstall` | `sudo ./deploy.sh uninstall` |
| 手动轮换扫描 | `curl -X POST http://<主机>:<端口>/api/v1/rotations/run -H "Authorization: Bearer <token>"` | 同左 |
| 运行测试 | `cd backend && ./.venv/bin/pytest -q` | 同左 |
| 构建前端 | `cd frontend && npm run build` | 同左 |

---

## 12. 扩容方向（当前规模无需）

当前约 1000 台设备的纳管规模下单机完全够用。若未来规模增长（数万账号、高并发登录）：
API 层多副本 + Nginx/网关 upstream 负载均衡、数据库切换 PostgreSQL 并做主从、会话令牌短时效化 +
刷新令牌落 Redis 共享。以上均为配置级改动，业务代码无需重构。
