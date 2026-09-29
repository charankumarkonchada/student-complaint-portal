#!/usr/bin/env bash
# Helper script to launch IntelliHostel in development mode
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_ROOT"
export FLASK_DEBUG=1
export APP_ENV=development

python3 app.py
