import os
import json
from src.utils.safe_step import *

@safe_step
def write_json_per_msg(parsed, idx, out_dir):
    """
    Saves dictionary as JSON to a local drive.
    """
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"email_{idx:05d}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    return path
