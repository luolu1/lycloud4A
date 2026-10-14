#!/usr/bin/env bash
# =============================================================================
# lycloud4A 一键部署 / 更新脚本
#
# 支持三种部署方式：
#   compose  Docker Compose（推荐，单容器：前端 + 后端同端口）
#   docker   原生 Docker（docker build + docker run）
#   systemd  systemd + Nginx（裸机部署）
#
# 用法：
#   ./deploy.sh install [--mode compose|docker|systemd] [选项]
#   ./deploy.sh update  [--mode ...]          # 一键更新（重新构建 + 滚动重启）
#   ./deploy.sh start|stop|restart|status|logs|uninstall [--mode ...]
#   ./deploy.sh help
#
# 常用选项：
#   --mode <m>       部署方式（install 时必填；其它动作会读取安装时记录）
#   --port <p>       对外端口（默认 8000）
#   --dir <path>     systemd 模式安装目录（默认 /opt/4a-platform）
#   --domain <d>     systemd+Nginx 的 server_name（可选）
#   --tls-cert <f>   systemd 模式 TLS 证书路径（配合 --tls-key 启用 HTTPS）
#   --tls-key <f>    systemd 模式 TLS 私钥路径
#   --repo <url>     git 仓库地址（默认 luolu1/lycloud4A）
#   --branch <b>     git 分支（默认 main）
#   --no-nginx       systemd 模式不配置 Nginx（仅启动后端）
#   -y, --yes        跳过确认
# =============================================================================
set -euo pipefail

# ── 默认值 ───────────────────────────────────────────────────
REPO_URL="${REPO_URL:-https://github.com/luolu1/lycloud4A.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/4a-platform}"
PORT="${PORT:-8000}"
DOMAIN=""
TLS_CERT=""
TLS_KEY=""
USE_NGINX=1
ASSUME_YES=0
MODE=""
ACTION=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SERVICE_NAME="lycloud4a"
CONTAINER_NAME="lycloud4a"
IMAGE_NAME="lycloud4a:latest"
DATA_VOLUME="lycloud4a-data"
NGINX_CONF="/etc/nginx/conf.d/lycloud4a.conf"

# ── 颜色输出 ─────────────────────────────────────────────────
c_reset='\033[0m'; c_blue='\033[1;34m'; c_green='\033[1;32m'
c_yellow='\033[1;33m'; c_red='\033[1;31m'
log()  { printf "${c_blue}▶${c_reset} %s\n" "$*"; }
ok()   { printf "${c_green}✔${c_reset} %s\n" "$*"; }
warn() { printf "${c_yellow}!${c_reset} %s\n" "$*" >&2; }
die()  { printf "${c_red}✘${c_reset} %s\n" "$*" >&2; exit 1; }
need_cmd() { command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1（请先安装）"; }

confirm() {
  [ "$ASSUME_YES" -eq 1 ] && return 0
  read -r -p "$1 [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]]
}

# ── 状态文件（记录安装方式，供 update 等动作复用）────────────
state_dir() {
  if [ -n "${LYCLOUD4A_STATE_DIR:-}" ]; then echo "$LYCLOUD4A_STATE_DIR"; return; fi
  if [ "$(id -u)" -eq 0 ] && [ -w /etc ] 2>/dev/null; then echo "/etc/lycloud4a"; return; fi
  echo "${XDG_CONFIG_HOME:-$HOME/.config}/lycloud4a"
}
STATE_FILE="$(state_dir)/deploy.conf"

save_state() {
  mkdir -p "$(dirname "$STATE_FILE")"
  cat > "$STATE_FILE" <<EOF
MODE=$MODE
REPO_DIR=$REPO_DIR
INSTALL_DIR=$INSTALL_DIR
PORT=$PORT
DOMAIN=$DOMAIN
TLS_CERT=$TLS_CERT
TLS_KEY=$TLS_KEY
USE_NGINX=$USE_NGINX
REPO_URL=$REPO_URL
BRANCH=$BRANCH
EOF
  ok "已记录部署配置：$STATE_FILE"
}

load_state() {
  [ -f "$STATE_FILE" ] || return 1
  # shellcheck disable=SC1090
  . "$STATE_FILE"
  return 0
}

# 自动探测已安装方式（无状态文件时兜底）
detect_mode() {
  if [ -f "$STATE_FILE" ]; then load_state; echo "$MODE"; return; fi
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}\.service"; then
    echo systemd; return
  fi
  if command -v docker >/dev/null 2>&1 && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER_NAME"; then
    if docker inspect "$CONTAINER_NAME" --format '{{ index .Config.Labels "com.docker.compose.project" }}' 2>/dev/null | grep -q .; then
      echo compose; return
    fi
    echo docker; return
  fi
  return 1
}

# ── 参数解析 ─────────────────────────────────────────────────
parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      install|update|start|stop|restart|status|logs|uninstall|help|-h|--help)
        ACTION="$1"; shift ;;
      --mode) MODE="${2:-}"; shift 2 ;;
      --mode=*) MODE="${1#*=}"; shift ;;
      --port) PORT="${2:-}"; shift 2 ;;
      --port=*) PORT="${1#*=}"; shift ;;
      --dir) INSTALL_DIR="${2:-}"; shift 2 ;;
      --dir=*) INSTALL_DIR="${1#*=}"; shift ;;
      --domain) DOMAIN="${2:-}"; shift 2 ;;
      --domain=*) DOMAIN="${1#*=}"; shift ;;
      --tls-cert) TLS_CERT="${2:-}"; shift 2 ;;
      --tls-key) TLS_KEY="${2:-}"; shift 2 ;;
      --repo) REPO_URL="${2:-}"; shift 2 ;;
      --branch) BRANCH="${2:-}"; shift 2 ;;
      --no-nginx) USE_NGINX=0; shift ;;
      -y|--yes) ASSUME_YES=1; shift ;;
      *) die "未知参数：$1（用 ./deploy.sh help 查看用法）" ;;
    esac
  done
  [ -n "$ACTION" ] || ACTION="help"
  case "$ACTION" in -h|--help) ACTION="help" ;; esac
}

# ── .env 生成（缺省自动生成强密钥）───────────────────────────
gen_env() {
  local dir="$1"
  local env_file="$dir/.env"
  if [ -f "$env_file" ]; then
    ok "沿用已有环境配置：$env_file"
    return
  fi
  [ -f "$dir/.env.example" ] || die "缺少 .env.example：$dir"
  local secret vault
  secret="$(openssl rand -hex 32)"
  # Fernet 密钥 = 32 字节 urlsafe base64
  vault="$(openssl rand -base64 32 | tr '+/' '-_')"
  cp "$dir/.env.example" "$env_file"
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${secret}|" "$env_file"
  sed -i "s|^VAULT_MASTER_KEY=.*|VAULT_MASTER_KEY=${vault}|" "$env_file"
  chmod 600 "$env_file" 2>/dev/null || true
  ok "已生成环境配置（含随机 SECRET_KEY / VAULT_MASTER_KEY）：$env_file"
  warn "备份好 VAULT_MASTER_KEY，丢失后托管密码将无法解密！"
}

# ── 仓库同步 ─────────────────────────────────────────────────
sync_repo() {
  local dir="$1"
  if [ -d "$dir/.git" ]; then
    git config --global --add safe.directory "$dir" >/dev/null 2>&1 || true
    log "拉取最新代码（$BRANCH）…"
    git -C "$dir" fetch --all --prune
    git -C "$dir" checkout "$BRANCH"
    git -C "$dir" pull --ff-only
    ok "代码已更新到 $(git -C "$dir" rev-parse --short HEAD)"
  else
    warn "$dir 不是 git 仓库，跳过代码拉取（直接使用当前文件）"
  fi
}

# =============================================================================
# Docker 相关
# =============================================================================
compose_cmd() {
  if docker compose version >/dev/null 2>&1; then echo "docker compose";
  elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose";
  else die "未找到 docker compose / docker-compose"; fi
}

mode_compose() {
  need_cmd docker
  local cc; cc="$(compose_cmd)"
  case "$ACTION" in
    install)
      sync_repo "$REPO_DIR"
      gen_env "$REPO_DIR"
      log "构建并启动容器（$cc up -d --build）…"
      ( cd "$REPO_DIR" && $cc up -d --build )
      ok "Docker Compose 部署完成，访问 http://<主机>:$PORT"
      ;;
    update)
      sync_repo "$REPO_DIR"; gen_env "$REPO_DIR"
      log "重新构建并滚动更新…"
      ( cd "$REPO_DIR" && $cc up -d --build --remove-orphans )
      ok "更新完成"
      ;;
    start|stop|restart) ( cd "$REPO_DIR" && $cc "$ACTION" ) ;;
    status) ( cd "$REPO_DIR" && $cc ps ) ;;
    logs)   ( cd "$REPO_DIR" && $cc logs -f --tail=200 ) ;;
    uninstall)
      confirm "确认停止并移除 Compose 服务（数据卷默认保留）？" || exit 0
      ( cd "$REPO_DIR" && $cc down )
      warn "数据卷 $DATA_VOLUME 仍保留，如需彻底清理：docker volume rm $DATA_VOLUME"
      ;;
    *) die "compose 模式不支持动作：$ACTION" ;;
  esac
}

mode_docker() {
  need_cmd docker
  case "$ACTION" in
    install)
      sync_repo "$REPO_DIR"; gen_env "$REPO_DIR"
      log "构建镜像 $IMAGE_NAME …"
      docker build -t "$IMAGE_NAME" "$REPO_DIR"
      docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
      log "启动容器 …"
      docker run -d --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        --env-file "$REPO_DIR/.env" \
        -e ENVIRONMENT="${ENVIRONMENT:-production}" \
        -e SERVE_FRONTEND=true \
        -e FRONTEND_DIST_DIR=/app/frontend/dist \
        -p "${PORT}:8000" \
        -v "${DATA_VOLUME}:/app/backend/data" \
        "$IMAGE_NAME"
      ok "Docker 部署完成，访问 http://<主机>:$PORT"
      ;;
    update)
      sync_repo "$REPO_DIR"; gen_env "$REPO_DIR"
      log "重新构建镜像 …"
      docker build -t "$IMAGE_NAME" "$REPO_DIR"
      log "替换容器（保留数据卷）…"
      docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
      docker run -d --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        --env-file "$REPO_DIR/.env" \
        -e ENVIRONMENT="${ENVIRONMENT:-production}" \
        -e SERVE_FRONTEND=true \
        -e FRONTEND_DIST_DIR=/app/frontend/dist \
        -p "${PORT}:8000" \
        -v "${DATA_VOLUME}:/app/backend/data" \
        "$IMAGE_NAME"
      ok "更新完成"
      ;;
    start|stop|restart) docker "$ACTION" "$CONTAINER_NAME" >/dev/null && ok "容器已 $ACTION" ;;
    status) docker ps --filter "name=$CONTAINER_NAME" ;;
    logs)   docker logs -f --tail=200 "$CONTAINER_NAME" ;;
    uninstall)
      confirm "确认停止并删除容器（数据卷默认保留）？" || exit 0
      docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
      warn "数据卷 $DATA_VOLUME 仍保留，如需彻底清理：docker volume rm $DATA_VOLUME"
      ;;
    *) die "docker 模式不支持动作：$ACTION" ;;
  esac
}

# =============================================================================
# systemd + Nginx
# =============================================================================
mode_systemd() {
  local run_user="4a" backend_dir="$INSTALL_DIR/backend" web_dir="$INSTALL_DIR/frontend"
  local venv="$backend_dir/.venv"

  case "$ACTION" in
    install|update)
      [ "$(id -u)" -eq 0 ] || die "systemd 模式需 root 权限（请用 sudo 执行）"
      need_cmd python3

      if [ "$ACTION" = "install" ]; then
        log "准备安装目录 $INSTALL_DIR …"
        id "$run_user" >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin "$run_user"
        mkdir -p "$INSTALL_DIR"
        if [ ! -d "$INSTALL_DIR/backend" ]; then
          if command -v git >/dev/null 2>&1; then
            log "克隆仓库 $REPO_URL → $INSTALL_DIR …"
            git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
          else
            die "安装目录为空且未安装 git，无法获取代码"
          fi
        fi
      else
        sync_repo "$INSTALL_DIR"
      fi

      # 后端依赖
      log "创建/更新 Python 虚拟环境并安装依赖 …"
      [ -d "$venv" ] || python3 -m venv "$venv"
      "$venv/bin/pip" install --upgrade pip >/dev/null
      "$venv/bin/pip" install -r "$backend_dir/requirements.txt"

      # 前端构建
      if command -v npm >/dev/null 2>&1; then
        log "构建前端产物 …"
        ( cd "$web_dir" && npm ci && npm run build )
      else
        warn "未安装 npm，跳过前端构建（将使用仓库内已有 frontend/dist）"
        [ -d "$web_dir/dist" ] || warn "frontend/dist 不存在，前端将不可用"
      fi

      # 环境变量
      gen_env "$INSTALL_DIR"

      # 数据目录权限
      mkdir -p "$backend_dir/data/audit_logs"
      chown -R "$run_user:$run_user" "$INSTALL_DIR"

      install_systemd_unit "$run_user" "$backend_dir"
      [ "$USE_NGINX" -eq 1 ] && install_nginx

      systemctl daemon-reload
      systemctl enable --now "$SERVICE_NAME" >/dev/null 2>&1 || systemctl restart "$SERVICE_NAME"
      systemctl restart "$SERVICE_NAME"
      ok "systemd 部署完成：systemctl status $SERVICE_NAME"
      ;;
    start|stop|restart) systemctl "$ACTION" "$SERVICE_NAME" ;;
    status) systemctl status "$SERVICE_NAME" --no-pager ;;
    logs)   journalctl -u "$SERVICE_NAME" -f -n 200 ;;
    uninstall)
      [ "$(id -u)" -eq 0 ] || die "需 root 权限"
      confirm "确认停止并卸载 $SERVICE_NAME（代码与数据默认保留）？" || exit 0
      systemctl disable --now "$SERVICE_NAME" >/dev/null 2>&1 || true
      rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
      systemctl daemon-reload
      [ -f "$NGINX_CONF" ] && rm -f "$NGINX_CONF" && nginx -s reload 2>/dev/null || true
      warn "安装目录 $INSTALL_DIR 与数据库仍保留，如需彻底清理请手动删除。"
      ;;
    *) die "systemd 模式不支持动作：$ACTION" ;;
  esac
}

install_systemd_unit() {
  local run_user="$1" backend_dir="$2"
  log "安装 systemd 单元 /etc/systemd/system/${SERVICE_NAME}.service …"
  cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=lycloud4A Platform Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=${run_user}
Group=${run_user}
WorkingDirectory=${backend_dir}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${backend_dir}/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${PORT} --proxy-headers --forwarded-allow-ips *
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=${backend_dir}/data

[Install]
WantedBy=multi-user.target
EOF
}

install_nginx() {
  command -v nginx >/dev/null 2>&1 || { warn "未安装 Nginx，跳过反向代理配置"; return; }
  local root="$INSTALL_DIR/frontend/dist"
  log "生成 Nginx 配置 $NGINX_CONF …"
  if [ -n "$TLS_CERT" ] && [ -n "$TLS_KEY" ]; then
    cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name ${DOMAIN:-_};
    return 301 https://\$host\$request_uri;
}
server {
    listen 443 ssl http2;
    server_name ${DOMAIN:-_};
    ssl_certificate     ${TLS_CERT};
    ssl_certificate_key ${TLS_KEY};
    root ${root};
    index index.html;
    location / { try_files \$uri \$uri/ /index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
    location /healthz { proxy_pass http://127.0.0.1:${PORT}/healthz; }
    location /readyz  { proxy_pass http://127.0.0.1:${PORT}/readyz; }
}
EOF
  else
    cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name ${DOMAIN:-_};
    root ${root};
    index index.html;
    location / { try_files \$uri \$uri/ /index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
    location /healthz { proxy_pass http://127.0.0.1:${PORT}/healthz; }
    location /readyz  { proxy_pass http://127.0.0.1:${PORT}/readyz; }
}
EOF
  fi
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx 2>/dev/null || nginx -s reload
    ok "Nginx 配置已生效"
  else
    warn "Nginx 配置校验失败，请检查 $NGINX_CONF"
  fi
}

# =============================================================================
# 主流程
# =============================================================================
usage() {
  cat <<'USAGE'
lycloud4A 一键部署 / 更新脚本

用法：
  ./deploy.sh install [--mode compose|docker|systemd] [选项]
  ./deploy.sh update  [--mode ...]                一键更新到最新版本
  ./deploy.sh start|stop|restart|status|logs|uninstall [--mode ...]

部署方式：
  compose   Docker Compose（推荐，单容器：前端 + 后端同端口）
  docker    原生 Docker（docker build + docker run）
  systemd   systemd + Nginx（裸机部署），install 时需 root

选项：
  --mode <m>       部署方式（install 必填；其余动作读取安装时记录）
  --port <p>       对外端口（默认 8000）
  --dir <path>     systemd 安装目录（默认 /opt/4a-platform）
  --domain <d>     systemd+Nginx server_name（可选）
  --tls-cert <f>   TLS 证书路径（配合 --tls-key 启用 HTTPS）
  --tls-key <f>    TLS 私钥路径
  --repo <url>     git 仓库（默认 GitHub HTTPS；服务器已配 SSH 可用 git@github.com:luolu1/lycloud4A.git）
  --branch <b>     git 分支（默认 main）
  --no-nginx       systemd 模式不配置 Nginx
  -y, --yes        跳过确认

示例：
  ./deploy.sh install --mode compose
  ./deploy.sh install --mode docker --port 80
  sudo ./deploy.sh install --mode systemd --domain iam.corp.example.com
  ./deploy.sh update
USAGE
}

parse_args "$@"

if [ "$ACTION" = "help" ]; then usage; exit 0; fi

# 解析部署方式
if [ -z "$MODE" ]; then
  MODE="$(detect_mode || true)"
  [ -n "$MODE" ] || die "未检测到已安装的部署方式，请在 install 时用 --mode 指定（compose|docker|systemd）"
fi

# install 时确定仓库目录
case "$MODE" in
  compose|docker)
    REPO_DIR="${REPO_DIR:-$SCRIPT_DIR}"
    [ -f "$REPO_DIR/Dockerfile" ] || die "在 $REPO_DIR 未找到 Dockerfile"
    export ENVIRONMENT="${ENVIRONMENT:-production}"
    ;;
  systemd)
    REPO_DIR="$INSTALL_DIR"
    ;;
  *) die "未知部署方式：$MODE（可选 compose|docker|systemd）" ;;
esac

log "部署方式：$MODE ｜ 动作：$ACTION"

case "$MODE" in
  compose) mode_compose ;;
  docker)  mode_docker ;;
  systemd) mode_systemd ;;
esac

# 记录状态（install/update 后）
if [ "$ACTION" = "install" ] || [ "$ACTION" = "update" ]; then
  save_state
  echo
  ok "完成。常用命令："
  case "$MODE" in
    compose|docker) echo "    ./deploy.sh logs     查看日志" ;;
    systemd)        echo "    journalctl -u $SERVICE_NAME -f   查看日志" ;;
  esac
  echo "    ./deploy.sh update   一键更新到最新版本"
fi
