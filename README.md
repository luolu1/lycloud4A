# lycloud4A — 统一身份认证与访问管理平台

一套轻量、可自研维护的 4A 平台（认证 Authentication / 授权 Authorization / 账号 Account / 审计 Audit），
面向 **运维团队规模小于 10 人** 的组织，覆盖约 1000 台网络设备、安全设备、服务器及 Web 应用的统一身份管理与终端会话审计场景。

## 功能特性

| 域 | 能力 |
|----|------|
| 认证（Authentication） | 密码登录（bcrypt）、**TOTP 双因素认证**、JWT 双 Token（access 30min + refresh 7d 自动续期）、登录防爆破（5 次失败锁定 15 分钟）、密码强度策略（≥12 位，含大小写/数字/特殊字符） |
| 授权（Authorization） | **RBAC**（内置超级管理员、身份管理员、安全审计员、密码托管管理员、只读用户、**运维用户** 等 6 个角色，27 个业务化权限码）+ **ABAC 策略**，支持策略求值接口预判访问 |
| 账号（Account） | 用户 / 用户组 / 组织架构树全生命周期管理；默认管理员 `admin` |
| 设备管理（Device Management） | 纳管服务器、交换机、防火墙、Web应用等基础设施；支持 SSH / Telnet / RDP / VNC / SFTP / FTP / Serial / HTTP / HTTPS 等协议；纳管自动探测连通性与手动状态检测 |
| 连接工具与客户端（lycloud4A） | 适配 MobaXterm、NetCatty、Xshell、SecureCRT、Chrome 等客户端；平台提供 **lycloud4A.exe** 本地连接助手安装包；一键启动本地工具并代入凭证；会话操作流自动实时录制并上报服务端归档 |
| 审计（Audit） | 认证、账号、授权、密码托管、设备连接**全量中文留痕**（操作人/时间/客户端访问真实IP/设备类型/连接工具/目标设备）；支持点击直接查阅终端会话完整操作日志流 |
| 密码托管（Vault） | 密钥凭证条目 + **不可变版本历史**、Fernet 加密存储、明文脱敏（掩码）、按需 reveal、**自动到期轮换**（APScheduler 定时扫描） |

## 技术栈

- **后端**：Python 3.11+ / FastAPI 0.115 / SQLAlchemy 2.0 / Pydantic 2 / PyJWT / bcrypt / pyotp / cryptography(Fernet) / APScheduler
- **前端**：Vite 5 / React 18 / TypeScript 5.6（strict）/ Ant Design 5 / axios / react-router-dom 6 / recharts / qrcode.react
- **数据库**：默认 SQLite（零运维），生产可切换 PostgreSQL（`psycopg2-binary` 已就绪）
- **部署**：systemd + Nginx 反向代理（模板位于 `deploy/`），亦可容器化

## 目录结构

```text
4a-platform/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（lifespan: init_db → seed → scheduler）
│   │   ├── core/              # 配置 / 数据库 / 安全原语(哈希·JWT·TOTP) / 加密(Fernet)
│   │   ├── models/            # SQLAlchemy 模型（用户/组织/RBAC/策略/应用/审计/密钥）
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── api/routers/       # 12 个路由：auth users groups orgs apps roles
│   │   │                      #   permissions policies audit secrets rotations dashboard
│   │   ├── services/          # rbac / policy / audit / secret / rotation / scheduler
│   │   ├── seed.py            # 幂等初始化（权限·内置角色·组织·示例数据）
│   │   └── ...
│   ├── tests/                 # pytest 端到端测试（13 项全绿）
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/               # axios 封装 + 路由端点（含 401 自动刷新 token）
│   │   ├── contexts/          # AuthContext（登录态 + 权限判断）
│   │   ├── components/        # ProtectedRoute（路由守卫 + 权限门）
│   │   ├── layouts/           # 主界布局（侧边菜单按权限渲染）
│   │   ├── pages/             # 登录 / 仪表盘 / 个人中心 / 账号 / 授权 / 审计 / 密码托管
│   │   └── types/             # 与后端契约对齐的 TS 类型
│   └── package.json
├── deploy/
│   ├── systemd/4a-backend.service   # 后端 systemd 单元
│   └── nginx/4a.conf                # Nginx 反代 + 前端静态托管
├── docs/
│   ├── api-contract.md        # API 契约（权威，勿改）
│   ├── architecture.md        # 架构设计
│   └── deployment.md          # 部署运维手册
└── Makefile
```

## 快速开始（开发环境）

```bash
# 1. 后端
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn app.main:app --reload --port 8000
#    Swagger UI: http://127.0.0.1:8000/docs

# 2. 前端（另开终端）
cd frontend
npm install
npm run dev                      # http://127.0.0.1:5173
```

首次启动自动完成：建表 → 植入 27 个权限码、5 个内置角色、示例组织/应用/密钥/策略 → 创建默认管理员。

> 默认管理员：`admin` / `Admin@12345`（请在生产环境通过环境变量修改，见 `docs/deployment.md`）

## 常用命令（Makefile）

```bash
make install        # 安装前后端依赖
make run-backend    # 启动后端 (uvicorn :8000)
make run-frontend   # 启动前端 (vite :5173)
make test           # 运行后端 pytest
make build          # 构建前端产物 (tsc --noEmit && vite build)
make seed           # 幂等植入种子数据
```

## 验证

```bash
cd backend && ./.venv/bin/pytest -q        # 13 passed
cd frontend && npm run build               # tsc --noEmit && vite build 通过
```

全链路冒烟：真实启动 uvicorn 走 HTTP 全流程（认证/CRUD/密码托管/轮换/审计/RBAC 隔离），
脚本见 `scripts/e2e_smoke.py`（`make smoke`），45 项断言全部 PASS。

## 文档导航

- [架构设计](docs/architecture.md) — 系统架构 / 模块职责 / 数据模型 / 认证与授权流程 / 安全设计
- [部署运维](docs/deployment.md) — 生产部署 / 环境变量 / 安全加固 / 备份恢复 / 健康检查
- [API 契约](docs/api-contract.md) — 全部接口定义（权威）