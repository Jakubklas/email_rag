
import os
import json
from collections import defaultdict
from datetime import datetime, timezone
from openai import OpenAI
from config import *


def load_files(email_dir):
    """Yields each JSON of TXT object from a directory."""
    for filename in os.listdir(email_dir):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(email_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            yield json.load(f)

def normalize_id(raw: str) -> str:
    return raw.strip("<>").lower()

def parse_iso(dt_str):
    """Converts email date format into ISO."""
    if not dt_str:
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        # normalize trailing Z → +00:00
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        # CHANGED: on any parse error, also fall back
        return datetime.min.replace(tzinfo=timezone.utc)


def build_thread_map(emails_dir: str) -> dict[str, str]:
    """
    Two-pass mapping:
      1) Read every message’s in_reply_to and references.
      2) For each message, walk up the chain to find the ultimate root.
    Returns { message_id_normalized: thread_root_id_normalized }.
    """
    msg_to_parent: dict[str, str | None] = {}
    msg_references: dict[str, list[str]] = {}

    # PASS 1: collect parent & references
    for fn in os.listdir(emails_dir):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(emails_dir, fn)
        with open(path, "r", encoding="utf-8") as f:
            e = json.load(f)

        mid  = normalize_id(e.get("message_id", ""))
        pid  = normalize_id(e.get("in_reply_to", "")) or None
        refs = [normalize_id(r) for r in e.get("references", [])]

        msg_to_parent[mid]  = pid
        msg_references[mid] = refs

    # PASS 2: find ultimate root per message
    def find_root(mid: str) -> str:
        pid = msg_to_parent.get(mid)
        # if we reply to a known message_id, follow it
        if pid and pid in msg_to_parent:
            root = find_root(pid)
            msg_to_parent[mid] = root  # path‐compress
            return root
        # else try the first reference we actually have
        for r in msg_references.get(mid, []):
            if r in msg_to_parent:
                return find_root(r)
        # no parent & no usable refs → self is root
        return mid

    return { mid: find_root(mid) for mid in msg_to_parent }


def build_attachments_map(parsed_attachments_dir):
    """
    Maps parsed attachment paths to the messages
    they were originally sent in via "message_id".
    """
    attach_map = defaultdict(list)
    for filename in os.listdir(parsed_attachments_dir):
        if not filename.endswith(".txt"):
            continue

        # filename format: _id_{msg_id}_id_{originalName}.txt
        parts = filename.split("_id_")
        msg_id     = parts[1]
        orig_filename   = parts[2]

        full_path  = os.path.join(parsed_attachments_dir, filename)
        attach_map[msg_id].append((orig_filename, full_path))
    
    return attach_map


def build_thread_docs(
    emails_dir: str,
    parsed_attachments_dir: str,
    thread_map: dict[str, str]
) -> dict[str, dict]:
    """
    Groups every email (and its .txt attachments) under its root-thread-id.
    Returns:
      { thread_id: {
           dates: [...],
           subjects: {...},
           participants: {...},
           texts: [...],
           message_ids: [...]
         }
      }
    """
    # build attachment lookup: msg_id → list of .txt paths
    attach_map = defaultdict(list)
    for fn in os.listdir(parsed_attachments_dir):
        if not fn.endswith(".txt"):
            continue
        parts = fn.split("_id_")
        if len(parts) < 3:
            continue
        mid = normalize_id(parts[1])
        attach_map[mid].append(os.path.join(parsed_attachments_dir, fn))

    # helper to parse ISO datetimes
    def parse_iso(dt_str):
        if not dt_str:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)

    # load & group
    threads = defaultdict(lambda: {
        "dates": [], "subjects": set(),
        "participants": set(), "texts": [],
        "message_ids": []
    })

    for fn in os.listdir(emails_dir):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(emails_dir, fn)
        with open(path, "r", encoding="utf-8") as f:
            e = json.load(f)

        mid = normalize_id(e.get("message_id", ""))
        tid = thread_map.get(mid, mid)
        ts  = parse_iso(e.get("date"))

        th = threads[tid]
        th["message_ids"].append(mid)
        th["dates"].append(ts)
        th["subjects"].add(e.get("subject", ""))
        th["participants"].update(e.get("participants", []))
        th["texts"].append(f"Message_{mid}: {e.get('body','')}")

        # include any attachment texts
        for att in attach_map.get(mid, []):
            with open(att, "r", encoding="utf-8") as af:
                atxt = af.read()
            th["dates"].append(ts)
            th["texts"].append(f"--Attachment_{os.path.basename(att)}: {atxt}")

    # sort each thread chronologically and clean up message_ids
    for tid, data in threads.items():
        entries = list(zip(
            data["dates"],
            data["texts"],
            data["message_ids"] + [None] * (len(data["texts"]) - len(data["message_ids"]))
        ))
        entries.sort(key=lambda x: x[0])
        dates, texts, mids = zip(*entries)
        data["dates"]       = list(dates)
        data["texts"]       = list(texts)
        data["message_ids"] = [m for m in mids if m]

    return threads


# def assemble_and_summarize(threads, thread_documents_dir):
#     """
#     Saves each thread as a JSON file and replaces the texts with a
#     LLM generated summary.
#     """
#     os.makedirs(thread_documents_dir, exist_ok=True)
#     client = OpenAI(api_key=SECRET_KEY)
#     counter = 0

#     for thread_id, data in threads.items():
#         try:
#             # 1) Compute metadata
#             first_date   = min(data["dates"]).isoformat()
#             last_date    = max(data["dates"]).isoformat()
#             subject      = next(iter(data["subjects"]))  # pick one
#             participants = list(data["participants"])

#             # 2) Build the full concatenated text
#             full_text = "\n\n".join(data["texts"])

#             # 3) Summarize with GPT-4o

#             chat_response   = client.chat.completions.create(
#                 model="gpt-4o",
#                 messages=[
#                     {"role":"system",
#                     "content":"Write a concise 2–3 sentence summary of this email thread, containing messages and attachemnts in a chronological order. Each block is labeled."},
#                     {"role":"user", "content": full_text[:15000]}
#                 ],
#                 temperature=0.2,
#             )

#             summary_text = chat_response.choices[0].message.content.strip()

#             thread_doc = {
#                 "type":             "thread",
#                 "thread_id":        thread_id,
#                 "subject":          subject,
#                 "participants":     participants,
#                 "first_date":       first_date,
#                 "last_date":        last_date,
#                 "summary_text":     summary_text,
#                 "doc_id":           f"{thread_id}_{counter}"
#             }

#             out_path = os.path.join(thread_documents_dir, f"{thread_id}.json")
#             with open(out_path, "w", encoding="utf-8") as f:
#                 json.dump(thread_doc, f, ensure_ascii=False, indent=2)
            
#             counter +=1
#             if counter % verbosity == 0:
#                 print(f"Threads summarized {counter+1}/{len(threads)}")
        
#         except Exception as e:
#             print(e)



