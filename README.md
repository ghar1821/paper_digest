# paper_digest

Daily arXiv paper digest for a computational biologist interested in cytometry, single-cell genomics, and AI/ML research.

## What it does

Fetches recent papers from selected arXiv categories (cs.LG, cs.AI, cs.NE, cs.CV, cs.CL), uses a local LLM (via [Ollama](https://ollama.com)) to filter and score them by relevance, and writes a ranked Markdown digest. Must-read papers (score ≥ 9) are automatically downloaded and converted to Markdown using [marker-pdf](https://github.com/VikParuchuri/marker).

## Scripts

- `fetch_papers_arxiv.py` — main pipeline: fetch → deduplicate → LLM filter/score → write digest → download must-reads
- `convert.py` — standalone PDF-to-Markdown converter (local file or arXiv URL)
- `main.py` — placeholder entrypoint

## Usage

```bash
# Run the daily digest
uv run fetch_papers_arxiv.py

# Convert a single paper
uv run convert.py --input https://arxiv.org/abs/2301.07041
uv run convert.py --input paper.pdf --output-dir ./output
```

## Requirements

- [uv](https://github.com/astral-sh/uv) for dependency management
- [Ollama](https://ollama.com) running locally with `gemma4:26b` pulled
- Output is written to `~/Documents/papers/digest/`
