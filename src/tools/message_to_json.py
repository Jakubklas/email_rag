import os
import json
from config import *


def write_json_per_msg(parsed, idx, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"email_{idx:05d}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    return path
