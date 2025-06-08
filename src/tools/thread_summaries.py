
import os
import json
from collections import defaultdict
from datetime import datetime
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


def parse_iso(dt_str):
    """Converts email date format into ISO."""
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


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


def build_thread_docs():
    """
    Builds a dictionary of all threads incl. chronologically ordered
    messages and attachemnts. Also includes the threas subject, participants
    and timestamps of each message in order to chronologically sort the text
    in each message + attachment combination.
    """
    attach_map = build_attachments_map(parsed_attachments_dir)

    # 1) Group all chunks by thread_id
    threads = defaultdict(lambda: {
        "dates": [],         # list of datetime
        "subjects": set(),   # unique subjects in this thread
        "participants": set(),
        "texts": []          # list of text blobs, parallel to "dates"
    })

    # 2) Load emails and their attachments
    for email in load_files(emails_dir):
        tid    = email["thread_id"]
        ts     = parse_iso(email["date"])
        subj   = email["subject"]
        parts  = email["participants"]
        body   = email["body"]
        msg_id = email["message_id"]

        thread = threads[tid]
        # email metadata
        thread["dates"].append(ts)
        thread["subjects"].add(subj)
        thread["participants"].update(parts)
        # email text
        thread["texts"].append(f"Message_{msg_id}: {body}")

        # attachments for this message—use same timestamp
        for orig_fn, path in attach_map.get(msg_id, []):
            with open(path, "r", encoding="utf-8") as af:
                atxt = af.read()
            thread["dates"].append(ts)
            thread["texts"].append(f"--Attachment_{orig_fn}: {atxt}")

    # 3) Sort each thread’s entries by timestamp (and keep the text aligned)
    for tid, data in threads.items():
        # If the thread ended up empty, skip sorting
        if not data["dates"]:
            continue

        # Pair up dates and texts, sort, then unzip
        entries = list(zip(data["dates"], data["texts"]))
        entries.sort(key=lambda x: x[0])
        dates_sorted, texts_sorted = zip(*entries)

        data["dates"] = list(dates_sorted)
        data["texts"] = list(texts_sorted)

    return threads


def assemble_and_summarize(threads, thread_documents_dir):
    """
    Saves each thread as a JSON file and replaces the texts with a
    LLM generated summary.
    """
    os.makedirs(thread_documents_dir, exist_ok=True)
    client = OpenAI(api_key=SECRET_KEY)
    counter = 0

    for thread_id, data in threads.items():
        try:
            # 1) Compute metadata
            first_date   = min(data["dates"]).isoformat()
            last_date    = max(data["dates"]).isoformat()
            subject      = next(iter(data["subjects"]))  # pick one
            participants = list(data["participants"])

            # 2) Build the full concatenated text
            full_text = "\n\n".join(data["texts"])

            # 3) Summarize with GPT-4o

            chat_response   = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role":"system",
                    "content":"Write a concise 2–3 sentence summary of this email thread, containing messages and attachemnts in a chronological order. Each block is labeled."},
                    {"role":"user", "content": full_text[:15000]}
                ],
                temperature=0.2,
            )

            summary_text = chat_response.choices[0].message.content.strip()

            thread_doc = {
                "type":             "thread",
                "thread_id":        thread_id,
                "subject":          subject,
                "participants":     participants,
                "first_date":       first_date,
                "last_date":        last_date,
                "summary_text":     summary_text
            }

            out_path = os.path.join(thread_documents_dir, f"{thread_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(thread_doc, f, ensure_ascii=False, indent=2)
            
            counter +=1
            if counter % verbosity == 0:
                print(f"Threads summarized {counter+1}/{len(threads)}")
        
        except Exception as e:
            print(e)



