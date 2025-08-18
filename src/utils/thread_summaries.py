import os
import json
import asyncio
from typing import Dict
import tiktoken
from openai import AsyncOpenAI
import aiofiles
from tenacity import retry, stop_after_attempt, wait_exponential
from config.config import *


tokenizer = tiktoken.get_encoding("cl100k_base")


def trim_to_tokens(text, max_tokens):
    """
    Trims email text to at max N tokens due to a large number
    of documnents to summarize.
    """
    tokens = tokenizer.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return tokenizer.decode(tokens[:max_tokens])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=30))
async def chat_completion_client(client, messages):
    """
    Creates OpenAI client with exp. backoff.
    """
    return await client.chat.completions.create(
        model=SUMMARY_MODEL,
        messages=messages,
        temperature=0.0
    )


async def summarize_and_write(thread_id, data, out_dir, client, sem):
    """
    Asynchronously summarize the whole email thread in 2-3 sentences
    & creates a JSON document per thread with thread metadata. 
    """
    async with sem:
        full_text = "\n\n".join(data["texts"])
        trimmed_text = trim_to_tokens(full_text, MAX_TOKENS_PER_PROMPT)

        messages = [
            {
                "role": "system",
                "content": "Write a concise, but detailed 2–3 sentence summary of this email thread."
            },
            {"role": "user", "content": trimmed_text}
        ]
        response = await chat_completion_client(client, messages)
        summary = response.choices[0].message.content.strip()

    first_date = min(data["dates"]).isoformat()
    last_date = max(data["dates"]).isoformat()
    subject = next(iter(data["subjects"]))
    participants = list(data["participants"])
    message_ids = data["message_ids"]

    thread_doc = {
        "type": "thread",
        "thread_id": thread_id,
        "subject": subject,
        "participants": participants,
        "first_date": first_date,
        "last_date": last_date,
        "message_ids": message_ids,
        "summary_text": summary,
        "doc_id": f"t_{thread_id}"          # Unique primary key for OpenSearch indexing 
    }

    out_path = os.path.join(out_dir, f"{thread_id}.json")
    async with aiofiles.open(out_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(thread_doc, ensure_ascii=False, indent=2))


async def async_assemble_and_summarize(threads, out_dir):
    """
    Orchestrates the batched asynchronous summaries &
    thread JSON creation.
    """
    os.makedirs(out_dir, exist_ok=True)
    client = AsyncOpenAI(api_key=SECRET_KEY)
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    items = list(threads.items())
    total = len(items)
    completed = 0

    for i in range(0, total, BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        tasks = [
            asyncio.create_task(summarize_and_write(tid, data, out_dir, client, sem))
            for tid, data in batch
        ]

        for co_routine in asyncio.as_completed(tasks):
            try:
                await co_routine
            except Exception as e:
                print(f"Error summarizing thread {e}")
            completed += 1
            if completed % VERBOSITY == 0 or completed == total:
                print(f"Summarized {completed}/{total} threads")