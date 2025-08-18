import os
import json
import asyncio
from openai import AsyncOpenAI
import aiofiles
from tenacity import retry, stop_after_attempt, wait_exponential
from src.utils.safe_step import safe_step
from config.config import *


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=30))
async def emb_client(client, text):
    """
    Creates OpenAI client embeddings model client with exp. backoff.
    """
    return await client.embeddings.create(
        model=EMB_MODEL,
        input=text
    )


async def embed_file(path, client, sem):
    """
    Reads thread JSON, generates embeddings for summary_text, and write back
    to the JSON document under the field 'embeddings'.
    """
    async with sem:
        # Open the JSON doc & extract the texts for embedding
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            content = json.loads(await f.read())

        text = content.get('summary_text')
        if not text:
            return False

        # Call embeddings model & write vectors back to dict
        resp = await emb_client(client, text)
        content['embedding'] = resp.data[0].embedding

        # Save & overwrite
        async with aiofiles.open(path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(content, ensure_ascii=False, indent=2))

    return True


@safe_step
async def async_embed_locations(dirs, doc_limit):
    """
    Orchestrates the embedding workflow over one or more 
    file directories.
    """
    client = AsyncOpenAI(api_key=SECRET_KEY)
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    for dir in dirs:
        print(f"Embedding files in '{dir}'…")
        files = [file for file in os.listdir(dir)]
        total = len(files)
        if total == 0:
            print("Error, no JSON files found)")
            continue

        limit = doc_limit if doc_limit is not None else total
        items = files[:limit]

        # Batch embed the files in each directory
        completed = 0
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i:i + BATCH_SIZE]
            tasks = [
                asyncio.create_task(embed_file(os.path.join(dir, filename), client, sem))
                for filename in batch
            ]

            for co_routine in asyncio.as_completed(tasks):
                try:
                    await co_routine
                except Exception as e:
                    print(f"Error embedding {dir}: {e}")
                completed += 1
                if completed % VERBOSITY == 0 or completed == limit:
                    print(f"Files embedded: {completed}/{limit}")
    print("\nAll embeddings were generated.\n")


def main(doc_limit=None):
    locations = [thread_documents_dir]
    asyncio.run(async_embed_locations(locations, doc_limit))


if __name__ == '__main__':
    main()
