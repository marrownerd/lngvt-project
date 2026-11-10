from longevity.open_access import _article_xml_to_text


def test_jats_xml_text_includes_sections_and_table_rows():
    xml = '''<?xml version="1.0"?>
    <article xmlns="http://www.niso.org/standards/z39-96/ns/jats">
      <front><article-meta><title-group><article-title>Example article</article-title></title-group></article-meta></front>
      <body><sec><title>Results</title><p>The adjusted hazard ratio was 0.82 (95% CI 0.74-0.91).</p>
      <table-wrap><table><tbody><tr><td>HR</td><td>0.82</td><td>0.74-0.91</td></tr></tbody></table></table-wrap>
      </sec></body>
    </article>'''
    text = _article_xml_to_text(xml)
    assert "Results" in text
    assert "hazard ratio was 0.82" in text
    assert "TABLE ROW: HR | 0.82 | 0.74-0.91" in text


def test_cached_full_text_is_preferred_and_keeps_cached_pmcid(tmp_path, monkeypatch):
    from longevity import open_access
    from longevity.effect_extraction import extract_from_papers
    monkeypatch.setattr(open_access, "CACHE_DIR", tmp_path)
    full_text = "Results\nThe hazard ratio was 0.82 (95% CI 0.74–0.91)."
    (tmp_path / "123.txt").write_text(full_text, encoding="utf-8")
    (tmp_path / "123.pmcid").write_text("PMC999", encoding="utf-8")
    rows = extract_from_papers([{
        "pmid": "123", "title": "Paper", "abstract": "No numerical result in abstract.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
    }])
    assert len(rows) == 1
    assert rows[0]["source_type"] == "Europe PMC OA full text (cached)"
    assert rows[0]["source_url"] == "https://europepmc.org/articles/PMC999"


def test_pmcid_alone_does_not_bypass_europe_pmc_open_access_check(monkeypatch, tmp_path):
    from longevity import open_access
    monkeypatch.setattr(open_access, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(open_access, "_resolve_pmcid", lambda pmid, timeout=25: (None, "Not marked open access"))
    result = open_access.fetch_open_access_full_text({"pmid": "123", "pmcid": "PMC123"})
    assert result["status"] == "unavailable"
    assert result["reason"] == "Not marked open access"
