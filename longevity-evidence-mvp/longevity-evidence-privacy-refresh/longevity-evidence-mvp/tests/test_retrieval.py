from longevity import retrieval


def test_retrieve_returns_title_and_abstract_matches(monkeypatch):
    papers = [
        {"pmid": "1", "title": "Resistance training and healthy aging",
         "abstract": "A study of exercise interventions in older adults.", "pub_date": "2025"},
        {"pmid": "2", "title": "Sleep duration and health",
         "abstract": "This paper studies sleep patterns.", "pub_date": "2024"},
    ]
    monkeypatch.setattr(retrieval, "list_papers", lambda limit: papers)
    hits = retrieval.retrieve("resistance training healthy aging", k=5)
    assert hits
    assert hits[0]["paper"]["pmid"] == "1"
    assert 0 <= hits[0]["score"] <= 1


def test_retrieve_empty_query_returns_empty_without_loading_db(monkeypatch):
    monkeypatch.setattr(retrieval, "list_papers", lambda limit: (_ for _ in ()).throw(AssertionError()))
    assert retrieval.retrieve("   ") == []


def test_retrieve_returns_empty_for_empty_library(monkeypatch):
    monkeypatch.setattr(retrieval, "list_papers", lambda limit: [])
    assert retrieval.retrieve("exercise") == []
