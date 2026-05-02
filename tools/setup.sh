#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
fi
echo "Setup complete. Edit .env with OPENROUTER_API_KEY and SELFIE_BIN."
