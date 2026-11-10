"""Run from the project root: python weekly.py"""
from longevity import db
from longevity.pipeline import run_weekly

if __name__ == "__main__":
    db.init_db()
    result = run_weekly(
        topics=["aging", "physical_activity", "sleep", "diet"],
        diseases=[],
        days=10,
        max_results=200
    )
    print(result)
