"""On-demand retrieval of Europe PMC open-access full text only."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from .config import DATA_DIR

EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
CACHE_DIR = DATA_DIR / "open_access_cache"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _node_text(node) -> str:
    return " ".join(" ".join(node.itertext()).split())


def _article_xml_to_text(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    blocks = []

    def walk(node):
        tag = _local_name(node.tag)
        if tag == "article-title":
            return
        if tag == "title":
            value = _node_text(node)
            if value:
                blocks.append(f"\n## {value}\n")
            return
        if tag == "p":
            value = _node_text(node)
            if value:
                blocks.append(value)
            return
        if tag == "tr":
            cells = []
            for cell in list(node):
                if _local_name(cell.tag) in {"td", "th"}:
                    cells.append(_node_text(cell))
            if any(cells):
                blocks.append("TABLE ROW: " + " | ".join(cells))
            return
        if tag in {"table-wrap-foot", "fn"}:
            value = _node_text(node)
            if value:
                blocks.append("TABLE/FOOTNOTE: " + value)
            return
        for child in list(node):
            walk(child)

    walk(root)
    # Deduplicate adjacent identical blocks that occur in nested JATS structures.
    clean = []
    for block in blocks:
        block = block.strip()
        if block and (not clean or clean[-1] != block):
            clean.append(block)
    return "\n\n".join(clean)


def _resolve_pmcid(pmid: str, timeout: int = 25):
    response = requests.get(
        f"{EUROPE_PMC}/search",
        params={"query": f"EXT_ID:{pmid}", "format": "json", "pageSize": 1},
        timeout=timeout,
        headers={"User-Agent": "LivingEvidenceEngine/0.2 (local research prototype)"},
    )
    response.raise_for_status()
    results = response.json().get("resultList", {}).get("result", [])
    if not results:
        return None, "No Europe PMC record found."
    item = results[0]
    pmcid = item.get("pmcid")
    if not pmcid or item.get("isOpenAccess") != "Y":
        return None, "No open-access full text is registered in Europe PMC."
    return pmcid, None


def load_cached_full_text(paper: dict):
    pmid = str(paper.get("pmid") or "")
    if not pmid:
        return None
    path = CACHE_DIR / f"{pmid}.txt"
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        return text if text.strip() else None
    except OSError:
        return None


def load_cached_pmcid(pmid: str):
    try:
        value = (CACHE_DIR / f"{pmid}.pmcid").read_text(encoding="utf-8").strip()
        return value or None
    except OSError:
        return None


def fetch_open_access_full_text(paper: dict, timeout: int = 45):
    """Fetch and cache OA text; returns a status dictionary and never bypasses licences/paywalls."""
    pmid = str(paper.get("pmid") or "")
    if not pmid or not re.fullmatch(r"\d+", pmid):
        return {"status": "skipped", "reason": "A valid PMID is required."}
    cached = load_cached_full_text(paper)
    if cached:
        return {"status": "cached", "pmcid": paper.get("pmcid") or load_cached_pmcid(pmid), "full_text": cached}

    # A PMCID alone does not prove that a record is open access. Always verify
    # the Europe PMC OA flag before requesting its full-text XML.
    try:
        resolved_pmcid, reason = _resolve_pmcid(pmid, timeout=min(timeout, 25))
    except requests.RequestException as exc:
        return {"status": "error", "reason": f"Europe PMC lookup failed: {exc}"}
    except (ValueError, KeyError) as exc:
        return {"status": "error", "reason": f"Could not parse Europe PMC response: {exc}"}
    if not resolved_pmcid:
        return {"status": "unavailable", "pmcid": paper.get("pmcid"), "reason": reason or "Full text unavailable."}
    pmcid = resolved_pmcid

    url = f"{EUROPE_PMC}/{pmcid}/fullTextXML"
    try:
        response = requests.get(
            url, timeout=timeout,
            headers={"User-Agent": "LivingEvidenceEngine/0.2 (local research prototype)"},
        )
        if response.status_code == 404:
            return {"status": "unavailable", "pmcid": pmcid, "reason": "Europe PMC has no full-text XML for this record."}
        response.raise_for_status()
        full_text = _article_xml_to_text(response.text)
        if not full_text.strip():
            return {"status": "unavailable", "pmcid": pmcid, "reason": "The OA XML record contained no extractable text blocks."}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{pmid}.txt").write_text(full_text, encoding="utf-8")
        (CACHE_DIR / f"{pmid}.pmcid").write_text(pmcid, encoding="utf-8")
        return {"status": "downloaded", "pmcid": pmcid, "full_text": full_text, "source_url": f"https://europepmc.org/articles/{pmcid}"}
    except requests.RequestException as exc:
        return {"status": "error", "pmcid": pmcid, "reason": f"Full-text request failed: {exc}"}
    except ET.ParseError as exc:
        return {"status": "error", "pmcid": pmcid, "reason": f"Could not parse full-text XML: {exc}"}
