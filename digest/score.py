"""LLM-based filtering and scoring of papers."""

import json
import time
from pathlib import Path

import ollama


def filter_and_score(
    papers: list[dict],
    model: str,
    max_results: int,
    prompt_path: Path,
) -> dict:
    """Ask the local LLM to filter and score a list of papers.

    Returns the parsed JSON object from the model response.
    """
    abstracts_text = ""
    for i, p in enumerate(papers):
        abstracts_text += (
            f"\n[{i}] TITLE: {p['title']}\n"
            f"AUTHORS: {p['authors']}\n"
            f"SOURCE: {p['source']} | {p['published']}\n"
            f"ABSTRACT: {p['abstract'][:500]}\n"
        )

    prompt_template = prompt_path.read_text()
    prompt = (
        prompt_template
        .replace("{num_papers}", str(len(papers)))
        .replace("{max_results}", str(max_results))
        .replace("{abstracts_text}", abstracts_text)
    )

    def _parse_json_from_raw(raw_text: str) -> dict:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        cleaned = cleaned.strip()
        if not cleaned:
            raise ValueError("Model returned empty content.")
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(cleaned[start : end + 1])
            raise

    last_err = None
    for attempt in range(1, 4):
        try:
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_ctx": 196608},
            )
            raw = (response or {}).get("message", {}).get("content", "")
            return _parse_json_from_raw(raw)
        except Exception as exc:
            last_err = exc
            print(
                f"  Warning: LLM response parse failed (attempt {attempt}/3): {exc}",
                flush=True,
            )
            time.sleep(2 * attempt)

    raise RuntimeError(
        "Failed to obtain valid JSON from LLM after 3 attempts."
    ) from last_err
