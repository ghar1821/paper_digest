"""Format the digest as Markdown and download must-read PDFs."""

from datetime import datetime
from pathlib import Path

from .convert import convert_pdf, download_arxiv_pdf, parse_arxiv_url


def format_digest(
    selected: list[dict],
    papers: list[dict],
    model: str,
    today: datetime,
    datetime_str: str,
) -> str:
    """Render the scored paper list as a Markdown digest string."""
    day_str = today.strftime("%A %-d %B %Y")
    lines = [
        f"# 🧬 Paper Digest — {day_str}",
        f"*{len(papers)} papers reviewed · {len(selected)} included · "
        f"{model} · Generated 03:00*",
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
        f"*{len(papers)} reviewed · {len(selected)} included · {model} · {datetime_str}*"
    )
    return "\n".join(lines)


def download_must_reads(
    selected: list[dict],
    papers: list[dict],
    output_dir: Path,
    datetime_str: str,
) -> None:
    """Download and convert must-read papers (score >= 9) to Markdown."""
    must_reads = [s for s in selected if s["score"] >= 9]
    if not must_reads:
        print("No must-read papers (score >= 9) to download.", flush=True)
        return

    pdf_dir = output_dir / datetime_str / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"Downloading {len(must_reads)} must-read paper(s) to {pdf_dir} ...", flush=True
    )

    from marker.converters.pdf import PdfConverter  # noqa: F401 — imported for side effects
    from marker.models import create_model_dict
    from marker.output import text_from_rendered  # noqa: F401

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
