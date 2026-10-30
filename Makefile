# Common tasks. Run `make help`.
VERSION := $(shell cat VERSION)
IMAGE   ?= voicollo-lms
VENV    ?= backend/.venv
PY      := $(VENV)/bin/python

.PHONY: help install test lint format build-web image run release up down

help:                ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install:             ## Install backend (venv) and frontend dependencies
	python3 -m venv $(VENV) && $(PY) -m pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

test:                ## Backend tests
	cd backend && ../$(PY) -m pytest -q

lint:                ## Ruff + ESLint + TypeScript
	cd backend && ../$(VENV)/bin/ruff check . && ../$(VENV)/bin/ruff format --check .
	cd frontend && npm run lint && npx tsc -b

format:              ## Auto-format backend
	cd backend && ../$(VENV)/bin/ruff check --fix . && ../$(VENV)/bin/ruff format .

build-web:           ## Production build of the SPA
	cd frontend && npm run build

image:               ## Build $(IMAGE):$(VERSION)
	IMAGE=$(IMAGE) scripts/build-image.sh

up:                  ## Run the full stack from source (uses deploy/.env)
	cd deploy && docker compose -f docker-compose.yml -f docker-compose.build.yml up --build -d

down:                ## Stop the stack
	cd deploy && docker compose -f docker-compose.yml -f docker-compose.build.yml down

release:             ## Prepare a release: make release V=2.1.0
	scripts/release.sh $(V)
