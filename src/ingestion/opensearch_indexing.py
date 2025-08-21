import os
import json
import time
from opensearchpy import helpers
from src.utils.clients import create_os_client
from src.utils.safe_step import safe_step
from config.config import *


@safe_step
def wipe_os_index(client, index_name):
    """
    Deletes the previous index to get a clean slate & no overlap.
    """
    if client.indices.exists(index_name):
        client.indices.delete(index=index_name)
        print(f"Cleaned the index {index_name}")
    else:
        print(f"No available index with name: {index_name}. Continuing.")


@safe_step
def create_os_index(client, index_name):
    """
    Creates a fresh index, deleting any index with
    the same name.
    """
    try:
        # Create the mapping (identical to the JSON structure)
        if not client.indices.exists(index_name):
            print(f"Creating index {index_name!r}\n")
            mapping = {
                "settings": {
                    "index": {
                        "knn": True
                    }
                },
                "mappings": {
                    "dynamic": True,
                    "properties": {
                        "doc_id":       {"type": "keyword"},
                        "thread_id":    {"type": "keyword"},
                        "message_id":   {"type": "keyword"},
                        "embedding":    {"type": "knn_vector", "dimension": 1536},
                        "type":         {"type": "keyword"},
                        "date":         {"type": "date"},
                        "subject":      {"type": "text"},
                        "body":         {"type": "text"},
                        "summary_text": {"type": "text"},
                        "participants": {"type": "keyword"},
                        "links": {
                            "type":   "object",
                            "dynamic": False
                        }
                    }
                }
            }
            client.indices.create(index=index_name, body=mapping)
            print(f"Index {index_name} created.")
    except Exception as e:
        print(f"Error, creating index failed due to: {e}")


@safe_step
def actions_generator(dirs_to_index, index_name, doc_limit=None):
    """
    Generates one document indexing action at a time for efficient
    memory handling. Skips files on errors.
    """
    for directory in dirs_to_index:
        if doc_limit is None:
            doc_limit = len(os.listdir(directory))
            
        print(f"Indexing data from directory: '{directory}'")
        for filename in os.listdir(directory)[:doc_limit]:
            if not filename.endswith(".json"):
                continue

            path = os.path.join(directory, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    doc = json.load(f)

                if not doc.get("date"):
                    doc.pop("date", None)
                yield {
                    "_index":  index_name,
                    "_id":     doc.get("doc_id", filename),
                    "_source": doc
                }

            except Exception as e:
                print(f"Skipping file {filename!r} due to error: {e}")
                continue


@safe_step
def indexing_summary():
    """
    Reports on the the directory size ahead of indexing.
    """
    total = 0
    print("Total docs in each directory to index:")
    for i in DIRS_TO_INDEX:
        size = len(os.listdir(i))
        print(f"{size} docs in {i}")
        total += size
    print()
    print(f"Total of {total} documents ready to index.")




@safe_step
def stream_docs_to_os(index_name, client, doc_limit=None, batch_size=1000):
    """
    Indexes documents into OpenSearch in batches using a generator.
    Retries on file/connection errors & logs progress. 
    """
    print(f"Prepping to index documents in batches of {batch_size}")
    
    successes = 0
    errors = 0
    batch_count = 0
    backoff = 1
    
    # Iterate over gnerator actions in batches
    batch = []
    for action in actions_generator(DIRS_TO_INDEX, index_name, doc_limit):
        batch.append(action)
        
        if len(batch) >= batch_size:
            batch_count += 1
            try:
                succ_batch, err_batch = helpers.bulk(
                    client,
                    batch,
                    raise_on_error=False,
                    stats_only=True
                )
                successes += succ_batch
                errors += err_batch
                backoff = 1
                print(f"Batch {batch_count}: {successes} indexed, {errors} errors")
                batch = []

            # Back-off exponentially on each error & retry
            except Exception as e:
                if hasattr(e, "status_code"):
                    print(f"Starus Code: {e} on batch {batch_count}, backing off {backoff} seconds.")
                else:
                    print(f"Error on batch {batch_count}: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
    
    # Process the last partial batch
    if batch:
        batch_count += 1
        try:
            succ_batch, err_batch = helpers.bulk(
                client,
                batch,
                raise_on_error=False,
                stats_only=True
            )
            successes += succ_batch
            errors += err_batch
            print(f"Batch {batch_count}: {successes} indexed, {errors} errors")
        except Exception as e:
            print(f"[ERROR] Failed to index final batch: {e}")

    print(f"[DONE] Indexed {successes} docs with {errors} errors across {batch_count} batches.")
    print("Refreshing index…")
    client.indices.refresh(index=index_name)
    print("Index refreshed.")



def main(index_name=INDEX_NAME):
    # Authenticate to OpenSearch
    client = create_os_client(OPENSEARCH_ENDPOINT, MASTER_USER, MASTER_PASSWORD)
    if not client:
        print("No client created. Interrupting.")
        return

    # Prep -> Wipe existing & create new index & summarize 
    wipe_os_index(client, index_name)
    create_os_index(client, index_name)
    indexing_summary()

    # Index docs to OpenSearch
    stream_docs_to_os(index_name, client)

    # Report on results
    result = client.cat.count(index=index_name, format="json")
    if result:
        doc_count = result[0]["count"]
        print(f"Indexing complete. Total documents in index: {doc_count}")

