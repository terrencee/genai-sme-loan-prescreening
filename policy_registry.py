import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

REG_PATH = Path("policy_registry.json")

def _load() -> Dict:
    if REG_PATH.exists():
        return json.loads(REG_PATH.read_text(encoding="utf-8"))
    return {"policies": []}

def _save(db: Dict):
    REG_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

def add_policy_entry(entry: Dict):
    db = _load()
    db["policies"].append(entry)
    _save(db)

def set_policy_status(policy_id: str, status: str, approved_by: str = "analyst"):
    db = _load()
    for p in db["policies"]:
        if p["policy_id"] == policy_id:
            p["status"] = status
            p["status_updated_at"] = datetime.utcnow().isoformat()
            p["approved_by"] = approved_by
    _save(db)

def list_policies() -> List[Dict]:
    return _load()["policies"]