# VibeSight — tüm geliştirme komutları yerelde çalışır (CI'a bağımlı değildir).
# Gereksinimler: uv (https://docs.astral.sh/uv), Node.js 20+
.PHONY: help setup models dev backend frontend demo build serve check test lint format camera-test clean

BACKEND := cd backend &&
FRONTEND := cd frontend &&

help: ## Komutları listeler
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[1m%-13s\033[0m %s\n", $$1, $$2}'

setup: ## Bağımlılıkları kurar, modelleri indirir, pre-commit kancalarını etkinleştirir
	$(BACKEND) uv sync
	$(FRONTEND) npm ci
	$(MAKE) models
	@test -f backend/.env || cp backend/.env.example backend/.env
	-uvx pre-commit install

models: ## Çalışma zamanı modellerini indirir ve doğrular
	$(BACKEND) uv run python ../scripts/download_models.py

dev: ## Arka uç + arayüz (geliştirme modu, http://localhost:5173)
	@trap 'kill 0' INT TERM; \
	($(BACKEND) uv run vibesight) & \
	($(FRONTEND) npm run dev) & \
	wait

demo: ## Kamera olmadan demo verisiyle çalıştırır
	@trap 'kill 0' INT TERM; \
	($(BACKEND) VIBESIGHT_SOURCE=mock uv run vibesight) & \
	($(FRONTEND) npm run dev) & \
	wait

build: ## Arayüzü derler (sunucu tarafından tek portta sunulur)
	$(FRONTEND) npm run build

serve: build ## Üretim modu: http://127.0.0.1:8000
	$(BACKEND) uv run vibesight

camera-test: ## Tapo kamera bağlantısını test eder
	$(BACKEND) uv run python ../scripts/camera_test.py

lint: ## Statik kontroller
	$(BACKEND) uv run ruff check . ../scripts && uv run ruff format --check . ../scripts && uv run mypy vibesight
	$(FRONTEND) npm run lint && npm run typecheck

format: ## Kodu biçimlendirir
	$(BACKEND) uv run ruff check --fix . ../scripts && uv run ruff format . ../scripts

test: ## Testler
	$(BACKEND) uv run pytest -q

check: lint test build ## Commit/push öncesi tam kontrol (CI yerine)

clean: ## Derleme çıktılarını temizler
	rm -rf frontend/dist backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache
