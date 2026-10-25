.PHONY: run-server run-visualizer spawn-agent spawn-trained spawn-team run-agent-llm run run-web test lint install \
        train benchmark status kill-all \
        docker-build docker-up docker-up-orchestrator docker-down docker-logs docker-spawn-agent docker-shell

PYTHON ?= python
PYTHONPATH := $(CURDIR):$(CURDIR)/src:$(PYTHONPATH)
PORT ?= 7788
HOST ?= 127.0.0.1
AGENT_ID ?= trained_oracle
VIBE ?= explorer
EPISODES ?= 3000
TRIALS ?= 20
PERSONALITY ?=
API_KEY ?=
LLM_BACKEND ?= ollama
AGENT_DELAY ?= 0.8

# Prefer venv python when available
PY := $(if $(wildcard .venv/bin/python),.venv/bin/python,$(PYTHON))

install:
	$(PY) -m pip install -e ".[dev]"

# --- CLI & Simulation Management ---
status:
	$(PY) manage.py status

train:
	$(PY) manage.py train --episodes $(EPISODES)

benchmark:
	$(PY) manage.py benchmark --trials $(TRIALS)

spawn-agent:
	$(PY) manage.py spawn $(AGENT_ID) --type heuristic --vibe $(VIBE)

spawn-trained:
	$(PY) manage.py spawn $(AGENT_ID) --type trained --interval $(AGENT_DELAY)

spawn-team:
	$(PY) manage.py spawn-team

kill-all:
	$(PY) manage.py kill-all

run:
	PYTHONPATH=$(CURDIR)/src PORT=$(PORT) $(PY) main.py

run-web:
	PYTHONPATH=$(CURDIR)/src PORT=$(PORT) $(PY) main.py --no-visualizer --web

run-server:
	PYTHONPATH=$(CURDIR)/src $(PY) -m uvicorn api.main:app --host $(HOST) --port $(PORT) --reload

run-visualizer:
	UNDERWORLD_API_URL=http://$(HOST):$(PORT) PYTHONPATH=$(CURDIR)/src $(PY) src/visualizer.py

run-agent-llm:
	PYTHONPATH=$(CURDIR)/src UNDERWORLD_API_URL=http://$(HOST):$(PORT) $(PY) src/agents/agent_llm.py \
		--name $(AGENT_ID) --personality "$(PERSONALITY)" --api_key "$(API_KEY)" \
		--backend $(LLM_BACKEND) --delay $(AGENT_DELAY)

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

# --- Docker Targets ---
docker-build:
	docker compose build

docker-up:
	docker compose up -d underworld

docker-up-orchestrator:
	docker compose --profile orchestrator up -d underworld-orchestrator

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-spawn-agent:
	docker compose exec underworld python src/agents/agent_simple.py --agent-id $(AGENT_ID) --vibe $(VIBE)

docker-shell:
	docker compose exec underworld /bin/bash
