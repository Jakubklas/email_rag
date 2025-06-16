from src.tools.thread_summaries import *
import os
import json
import asyncio
from typing import Dict, Tuple

from openai import AsyncOpenAI
import aiofiles  # pip install aiofiles :contentReference[oaicite:7]{index=7}
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential
)  # pip install tenacity :contentReference[oaicite:8]{index=8}
import tiktoken  # pip install tiktoken :contentReference[oaicite:9]{index=9}

# --- Configuration ---
MAX_CONCURRENT        = 20        # tune to your RPS/quota
BATCH_SIZE            = MAX_CONCURRENT * 2
PROGRESS_STEP         = 50
MAX_TOKENS_PER_PROMPT = 3000

# --- Helper: Token-aware truncation ---
tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding :contentReference[oaicite:10]{index=10}

def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Trim text to at most `max_tokens`, preserving token boundaries."""
    tokens = tokenizer.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated = tokenizer.decode(tokens[:max_tokens])
    return truncated

# --- Helper: Retry on transient failures ---
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=1, max=60)
)
async def call_chat_completion(
    client: AsyncOpenAI,
    messages: list[Dict]
) -> Dict:
    """Call OpenAI ChatCompletion with exponential backoff."""
    return await client.chat.completions.create(
        model=SUMMARY_MODEL,
        messages=messages,
        temperature=0.2
    )

# --- Per-thread summarization task ---
async def summarize_and_write(
    thread_id: str,
    data: Dict,
    out_dir: str,
    client: AsyncOpenAI,
    sem: asyncio.Semaphore
) -> None:
    """Fetch summary for one thread and write JSON to disk."""
    async with sem:
        # build prompt and truncate by tokens
        full_text = "\n\n".join(data["texts"])
        prompt    = truncate_to_tokens(full_text, MAX_TOKENS_PER_PROMPT)

        # request summary
        messages = [
            {"role": "system",
             "content": "Write a concise, but detailed 2–3 sentence summary of this email thread."},
            {"role": "user", "content": prompt}
        ]
        resp = await call_chat_completion(client, messages)
        summary = resp.choices[0].message.content.strip()

    # assemble document
    first_date   = min(data["dates"]).isoformat()
    last_date    = max(data["dates"]).isoformat()
    subject      = next(iter(data["subjects"]))
    participants = list(data["participants"])
    message_ids  = data["message_ids"]

    thread_doc = {
        "type":         "thread",
        "thread_id":    thread_id,
        "subject":      subject,
        "participants": participants,
        "first_date":   first_date,
        "last_date":    last_date,
        "message_ids":  message_ids,
        "summary_text": summary,
        "doc_id":       f"t_{thread_id}"
    }

    # async write via aiofiles
    out_path = os.path.join(out_dir, f"{thread_id}.json")
    async with aiofiles.open(out_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(thread_doc, ensure_ascii=False, indent=2))

# --- Orchestrator ---
async def async_assemble_and_summarize(
    threads: Dict[str, Dict],
    out_dir: str
) -> None:
    os.makedirs(out_dir, exist_ok=True)
    client = AsyncOpenAI(api_key=SECRET_KEY)
    sem    = asyncio.Semaphore(MAX_CONCURRENT)

    items = list(threads.items())
    total = len(items)
    completed = 0

    # process in batches to limit memory & rate spikes 
    for i in range(0, total, BATCH_SIZE):
        batch = items[i : i + BATCH_SIZE]
        tasks = [
            asyncio.create_task(
                summarize_and_write(tid, data, out_dir, client, sem)
            )
            for tid, data in batch
        ]

        # report progress as tasks complete
        for coro in asyncio.as_completed(tasks):
            try:
                await coro
            except Exception as e:
                print(f"❌ Error summarizing thread {e}")
            completed += 1
            if completed % PROGRESS_STEP == 0 or completed == total:
                print(f"→ Summarized {completed}/{total} threads")

# --- Entry point ---
def main():
    print("Building thread maps…\n")
    thread_map   = build_thread_map(emails_dir)
    print("Assembling thread documents…\n")
    threads      = build_thread_docs(
        emails_dir,
        parsed_attachments_dir,
        thread_map
    )

    print("Starting async summarization…\n")
    asyncio.run(
        async_assemble_and_summarize(
            threads,
            thread_documents_dir
        )
    )

if __name__ == "__main__":
    main()
