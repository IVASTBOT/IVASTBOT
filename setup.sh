#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "== IVASTBOT setup script =="

# 1) Create virtual environment and install dependencies
if command -v uv >/dev/null 2>&1; then
  echo "Using 'uv' to create venv and sync dependencies (uv.lock / pyproject.toml aware)"
  uv venv
  uv sync
else
  echo "'uv' not found — falling back to python venv + pip"
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  if [ -f pyproject.toml ]; then
    echo "Installing project in editable mode (pyproject.toml detected)"
    pip install -e .
  elif [ -f requirements.txt ]; then
    pip install -r requirements.txt
  else
    echo "No pyproject.toml or requirements.txt found — please install dependencies manually"
  fi
fi

# 2) Ensure .env exists (copy from example)
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "Created .env from .env.example — please edit .env to fill secrets"
  else
    echo "No .env.example found — please create .env before running"
  fi
else
  echo ".env already exists — leaving as is"
fi

# 3) Pull Ollama model (optional)
echo "\n== Ollama model pull (optional) =="
if command -v ollama >/dev/null 2>&1; then
  echo "Pulling model: qwen2.5:7b (skip if already present)"
  ollama pull qwen2.5:7b || true
else
  echo "ollama CLI not found — please install Ollama if you need local LLMs"
fi

# 4) Build ChromaDB index
echo "\n== Build ChromaDB index =="
read -p "Do you want to (re)build the ChromaDB now? [y/N] " yn
case "$yn" in
  [Yy]*)
    echo "Running: python backend/LLM.py build"
    python3 backend/LLM.py build
    ;;
  *)
    echo "Skipping ChromaDB build. You can run: python backend/LLM.py build"
    ;;
esac

echo "\nSetup finished. Check .env and run your app (e.g., uv run or python main.py)"
