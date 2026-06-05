import os
import json
import pandas as pd
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
STORE_PATH = os.path.join(DATA_DIR, "cancellations.parquet")
LOG_PATH = os.path.join(DATA_DIR, "upload_log.json")


def has_stored_data() -> bool:
    return os.path.exists(STORE_PATH)


def load_stored() -> pd.DataFrame:
    return pd.read_parquet(STORE_PATH)


def get_upload_log() -> list[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH) as f:
        return json.load(f)


def _save_log(log: list[dict]):
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)


def _rebuild_merged():
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    files = sorted([
        os.path.join(UPLOADS_DIR, f)
        for f in os.listdir(UPLOADS_DIR)
        if f.endswith(".parquet")
    ])
    if not files:
        if os.path.exists(STORE_PATH):
            os.remove(STORE_PATH)
        return
    parts = [pd.read_parquet(f) for f in files]
    combined = pd.concat(parts, ignore_index=True)
    combined = combined.drop_duplicates(subset=["conf_num"], keep="last")
    combined.to_parquet(STORE_PATH, index=False)


def merge_and_save(new_raw: pd.DataFrame, filename: str) -> tuple[pd.DataFrame, int, int]:
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    # Count new conf_nums before saving so we can compare against what already exists
    existing_confs: set = set()
    if has_stored_data():
        existing_confs = set(load_stored()["conf_num"].tolist())
    added = len(set(new_raw["conf_num"].tolist()) - existing_confs)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_") + os.urandom(2).hex()
    upload_path = os.path.join(UPLOADS_DIR, f"{ts}.parquet")
    new_raw.to_parquet(upload_path, index=False)

    _rebuild_merged()
    total = len(load_stored())

    log = get_upload_log()
    log.append({
        "id": ts,
        "filename": filename,
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "records_added": added,
        "total_after": total,
    })
    _save_log(log)

    return load_stored(), added, total


def delete_upload(upload_id: str):
    upload_path = os.path.join(UPLOADS_DIR, f"{upload_id}.parquet")
    if os.path.exists(upload_path):
        os.remove(upload_path)

    log = [e for e in get_upload_log() if e["id"] != upload_id]
    _save_log(log)
    _rebuild_merged()
