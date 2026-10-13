SHELL := /bin/bash
BACKEND := backend
FRONTEND := frontend
PY := $(BACKEND)/.venv/bin/python

.PHONY: help venv install install-backend install-frontend run-backend run-frontend dev test seed build smoke clean

help:
	@echo "4A 平台常用命令："
	@echo "  make install    安装前后端依赖"
	@echo "  make run-backend启动后端 (http://127.0.0.1:8000/docs)"
	@echo "  make run-frontend启动前端 (http://127.0.0.1:5173)"
	@echo "  make test       运行后端测试"
	@echo "  make build      构建前端产物"
	@echo "  make smoke      全链路 HTTP 冒烟（需后端依赖已安装）"

venv:
	cd $(BACKEND) && python3 -m venv .venv

install: install-backend install-frontend

install-backend:
	cd $(BACKEND) && ./.venv/bin/pip install -r requirements.txt

install-frontend:
	cd $(FRONTEND) && npm install

run-backend:
	cd $(BACKEND) && ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-frontend:
	cd $(FRONTEND) && npm run dev

test:
	cd $(BACKEND) && ./.venv/bin/pytest -q

seed:
	cd $(BACKEND) && ./.venv/bin/python -m app.seed

build:
	cd $(FRONTEND) && npm run build

smoke:
	./scripts/e2e_smoke.py

clean:
	rm -rf $(BACKEND)/.venv $(FRONTEND)/node_modules $(FRONTEND)/dist $(BACKEND)/data
