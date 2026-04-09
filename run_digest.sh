#!/usr/bin/env bash
# Runs the weekly paper digest via uv.
# Intended to be called by cron — logs to ~/Documents/papers/digest/logs/

set -euo pipefail

SCRIPT_DIR="$HOME/Documents/GitHub/paper_digest"
LOG_DIR="$HOME/Documents/papers/digest/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/digest-$(date +%Y-%m-%d).log"

echo "=== paper_digest started at $(date) ===" >> "$LOG_FILE"

# Launch Ollama if not already running, then wait for it to be ready
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama..." >> "$LOG_FILE"
    open -a Ollama >> "$LOG_FILE" 2>&1
    sleep 10
fi

cd "$SCRIPT_DIR"
"$SCRIPT_DIR/.venv/bin/python" fetch_papers_arxiv.py >> "$LOG_FILE" 2>&1
echo "=== paper_digest finished at $(date) ===" >> "$LOG_FILE"
