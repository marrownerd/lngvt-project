from . import db
from .pubmed import collect
from .extract import enrich
from .logging_utils import event

def run_weekly(topics, diseases=None, days=14, max_results=100):
    db.init_db()
    query = None
    run_id = db.start_run("pending")
    try:
        query, raw_papers = collect(topics, diseases, days, max_results)
        inserted = 0
        for paper in raw_papers:
            enriched = enrich(paper)
            if db.upsert_paper(enriched):
                inserted += 1
        db.finish_run(run_id, len(raw_papers), inserted, "success",
                      f"topics={topics}; diseases={diseases}")
        event("pipeline_finished", run_id=run_id, found=len(raw_papers), inserted=inserted)
        return {"run_id": run_id, "query": query, "found": len(raw_papers), "inserted": inserted}
    except Exception as exc:
        db.finish_run(run_id, 0, 0, "error", str(exc))
        event("pipeline_error", run_id=run_id, error=str(exc))
        raise
