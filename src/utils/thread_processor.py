import os
import json
import asyncio
from collections import defaultdict
from datetime import datetime, timezone

from config.config import *
from src.utils.safe_step import safe_step
from src.utils.thread_summaries import async_assemble_and_summarize


class ThreadProcessor:

    def __init__(
            self,
            emails_dir=emails_dir,
            parsed_attachments_dir=parsed_attachments_dir, 
            email_attachment_dir=email_attachment_dir,
            thread_documents_dir=thread_documents_dir
            ):
        self.emails_dir = emails_dir
        self.parsed_attachments_dir = parsed_attachments_dir
        self.email_attachment_dir = email_attachment_dir
        self.thread_documents_dir = thread_documents_dir
        

    def normalize_id(self, raw: str) -> str:
        """
        Normalizes the msg ID for consistency.
        """
        return raw.strip("<>").lower()
        

    def parse_iso(self, dt_str):
        """
        Changes email date format to ISO for consistency.
        """
        if not dt_str:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)


    @safe_step
    def build_thread_mapping(self):
        """
        For each email JSON reads every message's 'in_reply_to' + 'references'.
        Then moves up the chain to find the original message ID that started the
        thread. Then returns it as a dict {msg_id: thread_id}.
        """
        print("Identifying email threads...")
        
        msg_to_parent = {}
        msg_references = {}

        # Get parent message & references per message
        for doc in os.listdir(self.emails_dir):
            path = os.path.join(self.emails_dir, doc)
            with open(path, "r", encoding="utf-8") as f:
                email = json.load(f)

            msg_id  = self.normalize_id(email.get("message_id", ""))
            parent_id  = self.normalize_id(email.get("in_reply_to", "")) or None
            refs = [self.normalize_id(ref) for ref in email.get("references", [])]

            msg_to_parent[msg_id]  = parent_id
            msg_references[msg_id] = refs

        # Get the root msg_id per each chain (= thread_id)
        def _find_root(msg_id, visited=None):
            """
            Recursively finds the root email that started the thread.
            """
            if visited is None:
                visited = set()
            
            if msg_id in visited:
                return msg_id
            visited.add(msg_id)
            
            # Use parent_id to find its parent
            parent_id = msg_to_parent.get(msg_id)
            if parent_id is not None and parent_id in msg_to_parent:
                root = _find_root(parent_id, visited)
                msg_to_parent[msg_id] = root
                return root
            
            # If no parent_id, try with all references
            for ref in msg_references.get(msg_id, []):
                if ref in msg_to_parent:
                    return _find_root(ref, visited)
            
            # If no parent_id, nor refs, we found the root id
            return msg_id

        self.thread_map = {msg_id: _find_root(msg_id) for msg_id in msg_to_parent}
        return self.thread_map


    @safe_step
    def build_thread_docs(self):
        """
        Creates 'threads'; a dict containing 'message_ids', 'dates',
        'subjects', 'participants' and 'texts' for all messages &
        attachments under each email thread sorted chronologically.
        """
        # Create attachments map like {msg_id: [attach_id_1, attach_id_2]}
        attach_map = defaultdict(list)
        for file in os.listdir(self.parsed_attachments_dir):
            parts = file.split(id_marker)                   # id_marker coming from config.py -> used to indicate msg_id in file name
            if len(parts) < 3:
                continue
            msg_id = self.normalize_id(parts[1])
            attach_map[msg_id].append(os.path.join(self.parsed_attachments_dir, file))

        # Auto-initialize a pre-defined thread dict structure with new msg_id
        threads = defaultdict(lambda: {
            "dates": [], "subjects": set(),
            "participants": set(), "texts": [],
            "message_ids": []
        })

        # Load every email JSON & and add its thread_id to the thread_doc
        for file in os.listdir(self.emails_dir):
            path = os.path.join(self.emails_dir, file)
            with open(path, "r", encoding="utf-8") as f:
                email = json.load(f)

            msg_id = self.normalize_id(email.get("message_id", ""))
            thr_id = self.thread_map.get(msg_id, msg_id)
            timestamp  = self.parse_iso(email.get("date"))

            # Add data from message to the thread dict
            th = threads[thr_id]
            th["message_ids"].append(msg_id)
            th["dates"].append(timestamp)
            th["subjects"].add(email.get("subject", ""))
            th["participants"].update(email.get("participants", []))
            th["texts"].append(f"Message_{msg_id}: {email.get('body','')}")         # Will be replaced w/ LLM summary later

            # Add data from attachments to the thread dict
            for att in attach_map.get(msg_id, []):
                with open(att, "r", encoding="utf-8") as af:
                    att_text = af.read()
                th["dates"].append(timestamp)
                th["texts"].append(f"--Attachment_{os.path.basename(att)}: {att_text}")

        # Chronologically sort the messages in each thread
        for thr_id, data in threads.items():
            entries = []
            for i, (date, text) in enumerate(zip(data["dates"], data["texts"])):
                msg_id = data["message_ids"][i] if i < len(data["message_ids"]) else None
                entries.append((date, text, msg_id))
            
            entries.sort(key=lambda x: x[0])
            data["dates"] = [entry[0] for entry in entries]
            data["texts"] = [entry[1] for entry in entries]
            data["message_ids"] = [entry[2] for entry in entries if entry[2] is not None]

        self.threads = threads
        return threads


    @safe_step
    def annotate_threads(self, thread_map):
        """
        Adds a thread_id to each existing email JSON file.
        """
        # Open each email JSON and add the "thread_id" field
        for filename in os.listdir(self.emails_dir):
            path = os.path.join(self.emails_dir, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = json.load(f)

            msg_id = self.normalize_id(content.get("message_id", ""))
            content["thread_id"] = thread_map.get(msg_id)
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
                

    @safe_step
    def create_thread_summaries(self, thread_map):
        """
        First, builds threads with all email content. Then replaces the
        eamil texts with LLM generated summaries (used for embedded later).
        """
        print("Building thread documents...")
        thread_docs = self.build_thread_docs(thread_map)
        
        print("Asynchronously summarizing threads...")
        asyncio.run(async_assemble_and_summarize(thread_docs, self.thread_documents_dir))
        

    @safe_step
    def merge_emails_and_attachments(self):
        """
        Appends attachment texts to their email bodies
        using an 'Attachment:' text separator. Helps enrich the 
        email context for later RAG retrieval.
        """
        os.makedirs(self.email_attachment_dir, exist_ok=True)

        # Build a map like {msg_id : ['attachment_1', 'attachment_2']}
        attach_map = defaultdict(list)
        for filename in os.listdir(self.parsed_attachments_dir):
            parts = filename.split(id_marker)
            if len(parts) < 3:
                continue
            raw_msg_id = parts[1]
            msg_id = self.normalize_id(raw_msg_id)
            attach_map[msg_id].append(os.path.join(self.parsed_attachments_dir, filename))

        # Process each email & add attachments to it
        email_files = [f for f in os.listdir(self.emails_dir) if f.endswith('.json')]
        for idx, filename in enumerate(email_files, start=1):
            email_path = os.path.join(self.emails_dir, filename)
            with open(email_path, "r", encoding="utf-8") as f:
                email = json.load(f)

            msg_id = self.normalize_id(email.get("message_id", ""))
            merged_body = email.get("body", "")
            for att_path in attach_map.get(msg_id, []):
                try:
                    with open(att_path, "r", encoding="utf-8") as af:
                        att_text = af.read()
                    merged_body += (
                        f"\n\n--- Attachment: {os.path.basename(att_path)} ---\n"
                        f"{att_text}"
                    )
                except UnicodeDecodeError:
                    continue

            # Rebuild all email documents with the merged bodies
            merged = {
                **{k: v for k, v in email.items() if k != "body"},
                "body": merged_body,
                "doc_id": f"e_{msg_id}"
            }

            out_path = os.path.join(self.email_attachment_dir, filename)
            with open(out_path, "w", encoding="utf-8") as out:
                json.dump(merged, out, ensure_ascii=False, indent=2)

            if idx % 100 == 0:
                print(f"   → Merged {idx}/{len(email_files)} emails")
        print(f"Done: merged {len(email_files)} emails → {self.email_attachment_dir}")
        

    def process_threads(self, summarize=True):
        """
        Orchestrates the full thread creation flow.
        """
        # Build the map of thread_ids
        thread_map = self.build_thread_mapping()

        # Add a thread_id in each email JSON
        self.annotate_threads(thread_map)
        
        # Summarize each thread document with LLM
        if summarize:
            self.create_thread_summaries(thread_map)
            
        return thread_map