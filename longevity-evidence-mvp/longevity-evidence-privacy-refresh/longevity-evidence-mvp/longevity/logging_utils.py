import json
import logging
from datetime import datetime, timezone
from .config import LOG_PATH

logger = logging.getLogger("longevity")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

def event(name, **fields):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": name,
        **fields
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    logger.info("%s %s", name, json.dumps(fields, ensure_ascii=False, default=str))
