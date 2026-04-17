# paper_digest

Daily arXiv paper digest for a computational biologist interested in cytometry, single-cell genomics, and AI/ML research. Also includes a vault chat tool for querying an Obsidian vault with a local LLM.

## Repository structure

```
paper_digest/
├── digest/                     # Paper digest pipeline
│   ├── fetch.py                # Fetch and deduplicate papers from arXiv
│   ├── score.py                # LLM-based filtering and scoring
│   ├── format.py               # Markdown digest formatter + must-read PDF downloader
│   ├── convert.py              # PDF-to-Markdown converter (standalone CLI)
│   ├── run.py                  # Config and main pipeline entry point
│   └── prompt_filter_score.md  # Prompt template for the scoring LLM call
├── vault_chat/                 # Obsidian vault chat
│   └── chat.py                 # Multi-turn agentic loop over a local vault
├── run_digest.sh               # Shell wrapper for cron/launchd
└── pyproject.toml
```

## digest

Fetches recent papers from selected arXiv categories (cs.LG, cs.AI, cs.NE, cs.CV, cs.CL, cs.MA), uses a local LLM via [Ollama](https://ollama.com) to filter and score them by relevance, and writes a ranked Markdown digest. Must-read papers (score ≥ 9) are automatically downloaded and converted to Markdown using [marker-pdf](https://github.com/VikParuchuri/marker).

Configuration is at the top of [digest/run.py](digest/run.py):

| Variable | Default | Description |
|---|---|---|
| `MODEL` | `gemma4:26b` | Ollama model for scoring |
| `OUTPUT_DIR` | `~/Documents/papers/digest` | Where digests are written |
| `MAX_RESULTS` | `10` | Max papers to include in digest |
| `ARXIV_CATS` | see file | Categories and per-category fetch limits |

## vault_chat

A CLI tool that connects an [Obsidian](https://obsidian.md) vault to a local Ollama model via a multi-turn agentic loop. On startup it builds a file index from the vault and injects it into the conversation so the model knows what files are available. When the model needs to read a file it emits `READ: path/to/file.md`; the tool reads the file and feeds its contents back into the conversation.

Expected vault layout:

```
vault/
├── notes/          # .md files, one per source
├── glossary.md     # term definitions
├── to-read.md      # reading list
└── system/
    └── SKILL.md    # loaded as the system prompt on startup
```

Configuration is at the top of [vault_chat/chat.py](vault_chat/chat.py):

| Variable | Default | Description |
|---|---|---|
| `MODEL` | `llama3.2` | Ollama model for chat |
| `VAULT_PATH` | `~/vault` | Path to the Obsidian vault root |

## Usage

```bash
# Run the daily digest
uv run -m digest.run

# Convert a single paper to Markdown
uv run -m digest.convert --input https://arxiv.org/abs/2301.07041
uv run -m digest.convert --input paper.pdf --output-dir ./output

# Start the vault chat
uv run -m vault_chat.chat
```

Or use the installed scripts after `uv pip install -e .`:

```bash
run-digest
convert-pdf --input paper.pdf
vault-chat
```

## Requirements

- [uv](https://github.com/astral-sh/uv) for dependency management
- [Ollama](https://ollama.com) running locally with the configured models pulled
