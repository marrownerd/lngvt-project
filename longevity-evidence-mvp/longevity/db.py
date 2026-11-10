import sqlite3
import json
from datetime import datetime, timezone
from .config import DB_PATH

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            pmid TEXT PRIMARY KEY,
            doi TEXT,
            pmcid TEXT,
            title TEXT NOT NULL,
            abstract TEXT,
            pub_date TEXT,
            journal TEXT,
            authors TEXT,
            url TEXT,
            publication_types TEXT,
            mesh_terms TEXT,
            inferred_sexes TEXT,
            inferred_age_groups TEXT,
            inferred_diseases TEXT,
            inferred_topics TEXT,
            extraction_json TEXT,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK(id=1),
            age INTEGER,
            sex TEXT,
            diseases TEXT,
            interests TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            topic TEXT NOT NULL,
            description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pmid TEXT,
            rating INTEGER,
            note TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            query TEXT,
            found INTEGER DEFAULT 0,
            inserted INTEGER DEFAULT 0,
            status TEXT,
            details TEXT
        );
        """)
        # Backward-compatible schema migration for databases created by earlier MVP versions.
        columns = {row[1] for row in con.execute("PRAGMA table_info(papers)").fetchall()}
        if "pmcid" not in columns:
            con.execute("ALTER TABLE papers ADD COLUMN pmcid TEXT")
        defaults = [
            ("Regular physical activity", "physical_activity",
             "Research on physical activity, exercise, cardiorespiratory fitness and health outcomes."),
            ("Sleep duration and regularity", "sleep",
             "Research on sleep duration, sleep quality, circadian rhythm and health outcomes."),
            ("Diet quality", "diet",
             "Research on dietary patterns, nutrition and health outcomes."),
            ("Smoking cessation", "smoking",
             "Research on smoking, tobacco exposure and cessation."),
            ("Alcohol reduction", "alcohol",
             "Research on alcohol exposure and health outcomes."),
            ("Social connection", "social_connection",
             "Research on social relationships, isolation and health outcomes.")
        ]
        con.executemany("INSERT OR IGNORE INTO habits(name,topic,description) VALUES(?,?,?)", defaults)

def save_profile(age, sex, diseases, interests):
    with connect() as con:
        con.execute("""
        INSERT INTO profile(id,age,sex,diseases,interests,updated_at)
        VALUES(1,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET age=excluded.age, sex=excluded.sex,
        diseases=excluded.diseases, interests=excluded.interests, updated_at=excluded.updated_at
        """, (age, sex, json.dumps(diseases), json.dumps(interests),
              datetime.now(timezone.utc).isoformat()))

def get_profile():
    with connect() as con:
        row = con.execute("SELECT * FROM profile WHERE id=1").fetchone()
    if not row:
        return {"age": None, "sex": "not specified", "diseases": [], "interests": []}
    return {
        "age": row["age"], "sex": row["sex"],
        "diseases": json.loads(row["diseases"] or "[]"),
        "interests": json.loads(row["interests"] or "[]")
    }

def upsert_paper(p):
    with connect() as con:
        cur = con.execute("""
        INSERT OR IGNORE INTO papers
        (pmid,doi,pmcid,title,abstract,pub_date,journal,authors,url,publication_types,
         mesh_terms,inferred_sexes,inferred_age_groups,inferred_diseases,inferred_topics,
         extraction_json,fetched_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            p["pmid"], p.get("doi"), p.get("pmcid"), p["title"], p.get("abstract",""), p.get("pub_date"),
            p.get("journal"), json.dumps(p.get("authors",[])), p.get("url"),
            json.dumps(p.get("publication_types",[])), json.dumps(p.get("mesh_terms",[])),
            json.dumps(p.get("inferred_sexes",[])), json.dumps(p.get("inferred_age_groups",[])),
            json.dumps(p.get("inferred_diseases",[])), json.dumps(p.get("inferred_topics",[])),
            json.dumps(p.get("extraction",{})), datetime.now(timezone.utc).isoformat()
        ))
        return cur.rowcount == 1

def list_papers(limit=500):
    with connect() as con:
        rows = con.execute("SELECT * FROM papers ORDER BY pub_date DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ["authors","publication_types","mesh_terms","inferred_sexes",
                  "inferred_age_groups","inferred_diseases","inferred_topics","extraction_json"]:
            try: d[k] = json.loads(d[k] or "[]")
            except Exception: d[k] = []
        out.append(d)
    return out

def get_paper(pmid):
    with connect() as con:
        row = con.execute("SELECT * FROM papers WHERE pmid=?", (str(pmid),)).fetchone()
    if not row: return None
    d = dict(row)
    for k in ["authors","publication_types","mesh_terms","inferred_sexes",
              "inferred_age_groups","inferred_diseases","inferred_topics","extraction_json"]:
        try: d[k] = json.loads(d[k] or "[]")
        except Exception: d[k] = []
    return d

def save_feedback(pmid, rating, note):
    with connect() as con:
        con.execute("INSERT INTO feedback(pmid,rating,note,created_at) VALUES(?,?,?,?)",
                    (pmid, rating, note, datetime.now(timezone.utc).isoformat()))

def start_run(query):
    with connect() as con:
        cur = con.execute("INSERT INTO pipeline_runs(started_at,query,status) VALUES(?,?,?)",
                          (datetime.now(timezone.utc).isoformat(), query, "running"))
        return cur.lastrowid

def finish_run(run_id, found, inserted, status, details=""):
    with connect() as con:
        con.execute("""UPDATE pipeline_runs SET finished_at=?,found=?,inserted=?,status=?,details=?
                       WHERE id=?""",
                    (datetime.now(timezone.utc).isoformat(), found, inserted, status, details, run_id))

def recent_runs(limit=20):
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
