"""Fetch and deduplicate papers from arXiv."""

import time
import xml.etree.ElementTree as ET

import requests


def fetch_arxiv(cat: str, max_results: int) -> list[dict]:
    """Fetch the most recent papers from a single arXiv category."""
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


def deduplicate(papers: list[dict]) -> list[dict]:
    """Remove duplicate papers by title (case-insensitive)."""
    seen: set[str] = set()
    unique = []
    for p in papers:
        key = p["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique
