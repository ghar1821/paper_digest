import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import ollama
import requests

# allow importing convert.py from the same directory
sys.path.insert(0, str(Path(__file__).parent))
from convert import convert_pdf, download_arxiv_pdf, parse_arxiv_url

# ── Config ──────────────────────────────────────────────────────────────────
MODEL = "gemma4:26b"
OUTPUT_DIR = Path(__file__).parent / "output"
MAX_RESULTS = 10
TODAY = datetime.today()
DATETIME_STR = TODAY.strftime("%Y-%m-%d_%H-%M")

# ── arXiv categories to sweep ────────────────────────────────────────────────
ARXIV_CATS = [
    ("cs.LG", 150),
    ("cs.AI", 80),
    ("cs.NE", 50),
    ("cs.CV", 80),
    ("cs.CL", 80),
    ("cs.MA", 50),
]


# ── Fetch arXiv ──────────────────────────────────────────────────────────────
def fetch_arxiv(cat, max_results):
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query=cat:{cat}"
        f"&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={max_results}"
    )
    last_err = None
    for attempt in range(1, 6):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            break
        except Exception as exc:
            last_err = exc
            print(
                f"  Warning: fetch failed for {cat} (attempt {attempt}/5): {exc}",
                flush=True,
            )
            time.sleep(2 * attempt)
    else:
        raise RuntimeError(
            f"Failed to fetch arXiv:{cat} after 5 attempts"
        ) from last_err
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)
    papers = []
    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns).text.strip()
        abstract = entry.find("atom:summary", ns).text.strip()
        link = entry.find("atom:id", ns).text.strip()
        authors = ", ".join(
            a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)
        )
        published = entry.find("atom:published", ns).text[:10]
        papers.append(
            {
                "title": title,
                "abstract": abstract,
                "link": link,
                "authors": authors,
                "published": published,
                "source": f"arXiv:{cat}",
            }
        )
    return papers


# ── Deduplicate ──────────────────────────────────────────────────────────────
def deduplicate(papers):
    seen = set()
    unique = []
    for p in papers:
        key = p["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


# ── Ask  to filter and score ─────────────────────────────────────────────
def filter_and_score(papers):
    abstracts_text = ""
    for i, p in enumerate(papers):
        abstracts_text += (
            f"\n[{i}] TITLE: {p['title']}\n"
            f"AUTHORS: {p['authors']}\n"
            f"SOURCE: {p['source']} | {p['published']}\n"
            f"ABSTRACT: {p['abstract'][:500]}\n"
        )

    prompt = f"""
You are a research assistant for a computational biologist specialising in
cytometry data analysis, single-cell genomics, and AI/ML in biomedical research.

Her interests span two tracks:

Track 1 — Biomedical research:
Cytometry batch correction, single-cell foundation models, perturbation prediction,
ODEs and AI model mechanistic interpretability in biology, spatial transcriptomics,
multiomics data integration,
agentic AI for biological data analysis and prediction.

Track 2 — CS/AI horizon scanning:
LLM systems, world models, AI metacognition, how to build and understand AI models
better. No biomedical connection required — just substantive CS work.

Here are {len(papers)} paper abstracts from arXiv (cs.LG, cs.AI, cs.NE, cs.CV, cs.CL).
For each paper:
1. Decide if it belongs to Track 1, Track 2, or should be EXCLUDED
2. Exclude if: primary method is NMF/ICA/PCA/SVD/factor analysis with no neural
   component, pure clinical study, GWAS/epidemiology, pure gaming/robotics,
   stats department paper with statistical estimator as core contribution
3. Score relevance 1-10 within its track (never include below 5)
4. Flag AI slop if 3+ of these apply: vague unfalsifiable claim, benchmark
   circularity, missing ablations, implausible scope, no author web presence,
   superlative density without numbers, convenient self-serving benchmark,
   LLM phrasing patterns, no reproducibility statement
5. Write a 3-sentence summary: (1) what they built, (2) how, (3) key result
6. Write 1-2 sentences on why this paper is in the digest

Return ONLY valid JSON in this exact format — no prose, no markdown:
{{
  "selected": [
    {{
      "index": <original index>,
      "track": "Track 1" or "Track 2",
      "score": <1-10>,
      "slop": true or false,
      "vetted": "pass" or "marginal" or "fail",
      "summary": "<3 sentences>",
      "why": "<1-2 sentences>"
    }}
  ]
}}

Select the top {MAX_RESULTS} papers by score. Aim for roughly 7 Track 1
and 3 Track 2 papers but let score decide. Never include score below 5.
Never include vetted=fail papers.

Papers:
{abstracts_text}
"""

    def _parse_json_from_raw(raw_text):
        # strip any markdown fences if model adds them
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
            # try to salvage a JSON object embedded in extra text
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = cleaned[start : end + 1]
                return json.loads(snippet)
            raise

    last_err = None
    for attempt in range(1, 4):
        try:
            response = ollama.chat(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"num_ctx": 131072},
            )
            raw = (response or {}).get("message", {}).get("content", "")
            return _parse_json_from_raw(raw)
        except Exception as exc:
            last_err = exc
            print(
                f"  Warning: LLM response parse failed (attempt {attempt}/3): {exc}",
                flush=True,
            )
            # short backoff before retrying
            time.sleep(2 * attempt)

    # surface a clear error after retries are exhausted
    raise RuntimeError(
        "Failed to obtain valid JSON from LLM after 3 attempts."
    ) from last_err


# ── Format markdown output ───────────────────────────────────────────────────
def format_digest(selected, papers):
    day_str = TODAY.strftime("%A %-d %B %Y")
    lines = [
        f"# 🧬 Paper Digest — {day_str}",
        f"*{len(papers)} papers reviewed · {len(selected)} included · "
        f"{MODEL} · Generated 03:00*",
        "",
        "---",
        "",
    ]

    tiers = [
        ("⭐⭐⭐ Must-Read", lambda s: s["score"] >= 9),
        ("⭐⭐ Worth Reading", lambda s: 7 <= s["score"] <= 8),
        ("⭐ Skim / Bookmark", lambda s: 5 <= s["score"] <= 6),
    ]

    for tier_label, tier_filter in tiers:
        tier_papers = [s for s in selected if tier_filter(s)]
        if not tier_papers:
            continue
        lines.append(f"## {tier_label}")
        lines.append("")
        for s in tier_papers:
            p = papers[s["index"]]
            slop_flag = " 🤖⚠️" if s["slop"] else ""
            vet_flag = "⚠️" if s["vetted"] == "marginal" else "✅"
            lines += [
                f"### {p['title']}{slop_flag}",
                f"**Track:** {s['track']}  ",
                f"**Authors:** {p['authors']}  ",
                f"**Source:** {p['source']} · {p['link']} · "
                f"Published {p['published']}  ",
                f"**Relevance:** {s['score']}/10 · {vet_flag}",
                "",
                "**Why this digest:**  ",
                s["why"],
                "",
                "**Summary:**  ",
                s["summary"],
                "",
                "---",
                "",
            ]

    lines.append(
        f"*{len(papers)} reviewed · {len(selected)} included · {MODEL} · {DATETIME_STR}*"
    )
    return "\n".join(lines)


# ── Download + convert must-read papers ─────────────────────────────────────
def download_must_reads(selected, papers):
    must_reads = [s for s in selected if s["score"] >= 9]
    if not must_reads:
        print("No must-read papers (score >= 9) to download.", flush=True)
        return

    pdf_dir = OUTPUT_DIR / DATETIME_STR / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"Downloading {len(must_reads)} must-read paper(s) to {pdf_dir} ...", flush=True
    )

    # Load marker models once for all conversions
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered

    print("Loading marker models ...", flush=True)
    model_dict = create_model_dict()

    for s in must_reads:
        p = papers[s["index"]]
        arxiv_id = parse_arxiv_url(p["link"])
        if arxiv_id is None:
            print(f"  Skipping (could not parse arXiv ID): {p['link']}", flush=True)
            continue
        print(f"  [{s['score']}/10] {p['title'][:80]}", flush=True)
        try:
            pdf_path = download_arxiv_pdf(arxiv_id, pdf_dir)
            convert_pdf(pdf_path, pdf_dir, model_dict=model_dict)
        except Exception as exc:
            print(f"    Warning: failed — {exc}", flush=True)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Fetching arXiv...", flush=True)
    all_papers = []
    for cat, n in ARXIV_CATS:
        print(f"  {cat} ({n})", flush=True)
        all_papers.extend(fetch_arxiv(cat, n))

    print(f"Deduplicating {len(all_papers)} papers...", flush=True)
    all_papers = deduplicate(all_papers)
    print(f"  {len(all_papers)} unique papers", flush=True)

    print("Asking  to filter and score...", flush=True)
    result = filter_and_score(all_papers)
    selected = result["selected"]

    print(f"  {len(selected)} papers selected", flush=True)

    print("Writing digest...", flush=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"digest-{DATETIME_STR}.md"
    digest = format_digest(selected, all_papers)
    output_path.write_text(digest)
    print(f"  Written to {output_path}", flush=True)

    download_must_reads(selected, all_papers)


if __name__ == "__main__":
    main()
