import os
import json
import asyncio
from openai import AsyncOpenAI
import aiofiles
from tenacity import retry, stop_after_attempt, wait_exponential
from src.tools.safe_step import safe_step
from config import *

# Configuration
MAX_CONCURRENT = 20
BATCH_SIZE = MAX_CONCURRENT * 2
PROGRESS_STEP = 100

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=1, max=60)
)
async def call_embeddings(client: AsyncOpenAI, text: str):
    return await client.embeddings.create(
        model=EMBEDDINGS_MODEL,
        input=text
    )

async def embed_file(path: str, client: AsyncOpenAI, sem: asyncio.Semaphore):
    """
    Read JSON, generate embedding for chunk_text or summary_text, and write back.
    """
    async with sem:
        # Read document
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            content = json.loads(await f.read())

        # Determine text field
        doc_type = content.get('type')
        if doc_type in ('email', 'attachment'):
            text = content.get('chunk_text')
        elif doc_type == 'thread':
            text = content.get('summary_text')
        else:
            text = None

        if not text:
            return False  # skip

        # Call embeddings API with retry
        resp = await call_embeddings(client, text)
        vector = resp.data[0].embedding

        # Attach embedding and write back
        content['embedding'] = vector
        async with aiofiles.open(path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(content, ensure_ascii=False, indent=2))

    return True

async def async_embed_locations(locations: list[str], doc_limit: int | None):
    client = AsyncOpenAI(api_key=SECRET_KEY)
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    for location in locations:
        print(f"Embedding files in '{location}'…")
        files = [f for f in os.listdir(location) if f.endswith('.json')]
        total = len(files)
        if total == 0:
            print("  (no JSON files found)")
            continue

        limit = doc_limit if doc_limit is not None else total
        items = files[:limit]

        completed = 0
        # process in batches to avoid huge task lists
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i:i + BATCH_SIZE]
            tasks = [
                asyncio.create_task(embed_file(
                    os.path.join(location, fn), client, sem
                ))
                for fn in batch
            ]

            for coro in asyncio.as_completed(tasks):
                result = False
                try:
                    result = await coro
                except Exception as e:
                    print(f"❌ Error embedding {location}: {e}")
                completed += 1
                if completed % PROGRESS_STEP == 0 or completed == limit:
                    print(f"  → {completed}/{limit} embedded")

    print("All embeddings were generated.")

@safe_step
def main(embed_chunks=False, doc_limit=None):
    # Decide which directories to embed
    if embed_chunks:
        locations = [email_chunks_dir, attachment_chunks_dir, thread_documents_dir]
    else:
        print("[INFO] Skipping email & attachment embeddings for speed")
        locations = [thread_documents_dir]

    # Run async embedding pipeline
    asyncio.run(async_embed_locations(locations, doc_limit))

if __name__ == '__main__':
    main()
