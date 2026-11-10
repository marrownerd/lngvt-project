import sqlite3
from longevity import db


def test_old_database_gets_pmcid_column_and_still_accepts_papers(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(db, "DB_PATH", path)
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE papers (
        pmid TEXT PRIMARY KEY, doi TEXT, title TEXT NOT NULL, abstract TEXT,
        pub_date TEXT, journal TEXT, authors TEXT, url TEXT, publication_types TEXT,
        mesh_terms TEXT, inferred_sexes TEXT, inferred_age_groups TEXT,
        inferred_diseases TEXT, inferred_topics TEXT, extraction_json TEXT, fetched_at TEXT NOT NULL
    )""")
    con.commit()
    con.close()

    db.init_db()
    with db.connect() as con:
        columns = {row[1] for row in con.execute("PRAGMA table_info(papers)")}
    assert "pmcid" in columns

    assert db.upsert_paper({"pmid": "987", "title": "Migration test", "pmcid": "PMC123"})
    paper = db.get_paper("987")
    assert paper["pmcid"] == "PMC123"
