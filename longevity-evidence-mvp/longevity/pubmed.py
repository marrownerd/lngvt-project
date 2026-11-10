import os
import requests
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from .logging_utils import event

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

def _text(node, path):
    el = node.find(path)
    return "".join(el.itertext()).strip() if el is not None else ""

def build_query(topics, diseases=None):
    # PubMed syntax. The broad query is narrowed by topic/disease terms.
    terms = {
        "physical_activity": '("Exercise"[Mesh] OR "Physical Fitness"[Mesh] OR exercise[tiab] OR physical activity[tiab])',
        "sleep": '("Sleep"[Mesh] OR sleep[tiab] OR circadian[tiab])',
        "diet": '("Diet"[Mesh] OR diet[tiab] OR nutrition[tiab])',
        "smoking": '("Smoking Cessation"[Mesh] OR smoking[tiab] OR tobacco[tiab])',
        "alcohol": '("Alcohol Drinking"[Mesh] OR alcohol[tiab])',
        "social_connection": '("Social Isolation"[Mesh] OR social support[tiab] OR loneliness[tiab])',
        "aging": '("Aging"[Mesh] OR aging[tiab] OR ageing[tiab] OR longevity[tiab])'
    }
    chosen = [terms[t] for t in topics if t in terms]
    if not chosen:
        chosen = [terms["aging"]]
    query = "(" + " OR ".join(chosen) + ")"
    if diseases:
        disease_terms = " OR ".join(f'"{d}"[tiab]' for d in diseases)
        query += " AND (" + disease_terms + ")"
    return query

def search_pubmed(query, days=14, max_results=100):
    email = os.getenv("NCBI_EMAIL", "")
    api_key = os.getenv("NCBI_API_KEY", "")
    params = {
        "db": "pubmed", "term": query,
        "datetype": "pdat",
        "mindate": (date.today() - timedelta(days=days)).strftime("%Y/%m/%d"),
        "maxdate": date.today().strftime("%Y/%m/%d"),
        "retmax": max_results, "retmode": "json", "sort": "date"
    }
    if email: params["email"] = email
    if api_key: params["api_key"] = api_key
    r = requests.get(BASE + "esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])

def fetch_details(pmids):
    if not pmids: return []
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
    email = os.getenv("NCBI_EMAIL", "")
    api_key = os.getenv("NCBI_API_KEY", "")
    if email: params["email"] = email
    if api_key: params["api_key"] = api_key
    r = requests.get(BASE + "efetch.fcgi", params=params, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    results = []
    for art in root.findall(".//PubmedArticle"):
        citation = art.find(".//MedlineCitation")
        if citation is None: continue
        pmid = _text(citation, ".//PMID")
        title = _text(citation, ".//ArticleTitle")
        abstract_parts = []
        for a in citation.findall(".//Abstract/AbstractText"):
            label = a.attrib.get("Label", "")
            txt = "".join(a.itertext()).strip()
            if txt: abstract_parts.append((label + ": " if label else "") + txt)
        abstract = "\\n".join(abstract_parts)
        journal = _text(citation, ".//Journal/Title")
        doi = ""
        pmcid = None
        for aid in art.findall(".//ArticleId"):
            id_type = aid.attrib.get("IdType", "").lower()
            id_value = (aid.text or "").strip()
            if id_type == "doi":
                doi = id_value
            elif id_type in {"pmc", "pmcid"} and id_value:
                pmcid = id_value if id_value.upper().startswith("PMC") else f"PMC{id_value}"
        date_node = citation.find(".//Article/Journal/JournalIssue/PubDate")
        pub_date = ""
        if date_node is not None:
            year = _text(date_node, "Year")
            month = _text(date_node, "Month")
            day = _text(date_node, "Day")
            pub_date = "-".join(x for x in [year, month, day] if x)
        authors = []
        for au in citation.findall(".//AuthorList/Author"):
            collective = _text(au, "CollectiveName")
            name = " ".join(filter(None, [_text(au,"ForeName"), _text(au,"LastName")])) or collective
            if name: authors.append(name)
        pub_types = [_text(x, ".") for x in citation.findall(".//PublicationType")]
        mesh = [_text(x, ".") for x in citation.findall(".//MeshHeading/DescriptorName")]
        results.append({
            "pmid": pmid, "doi": doi or None, "pmcid": pmcid, "title": title or "Untitled",
            "abstract": abstract, "pub_date": pub_date or None, "journal": journal,
            "authors": authors[:8], "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "publication_types": pub_types, "mesh_terms": mesh
        })
    return results

def collect(topics, diseases=None, days=14, max_results=100):
    query = build_query(topics, diseases)
    ids = search_pubmed(query, days=days, max_results=max_results)
    papers = fetch_details(ids)
    event("pubmed_collection", query=query, found=len(papers), days=days)
    return query, papers
