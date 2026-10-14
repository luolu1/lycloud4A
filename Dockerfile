# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────
# lycloud4A 单镜像：多阶段构建（前端静态产物 + 后端运行时）
# 前端由后端直接托管，同一端口同时提供 SPA 与 /api，无需额外 Nginx。
# ─────────────────────────────────────────────────────────────

# ---------- 阶段 1：构建前端 ----------
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 阶段 2：运行时 ----------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    ENVIRONMENT=production \
    SERVE_FRONTEND=true \
    FRONTEND_DIST_DIR=/app/frontend/dist

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 后端依赖（单独一层，便于缓存）
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

# 后端源码 + 前端构建产物
COPY backend/ ./backend/
COPY --from=frontend-build /build/dist ./frontend/dist

# 非 root 运行；数据目录（SQLite / 会话日志）位于卷挂载点
RUN useradd --system --create-home --uid 10001 appuser \
    && mkdir -p /app/backend/data/audit_logs \
    && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
