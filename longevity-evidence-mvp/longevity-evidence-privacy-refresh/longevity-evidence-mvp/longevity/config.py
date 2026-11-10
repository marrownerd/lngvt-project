from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("LONGEVITY_DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "longevity.sqlite3"
LOG_PATH = DATA_DIR / "events.jsonl"
