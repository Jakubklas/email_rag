import os
import json
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
import boto3
from requests_aws4auth import AWS4Auth
from openai import OpenAI
from src.tools.safe_step import *
from config import *


# Authenticates to OpenSearch
@safe_step
def create_os_client(OPENSEARCH_ENDPOINT, MASTER_USER, MASTER_PASSWORD):
    client = OpenSearch(
    hosts=[{"host": OPENSEARCH_ENDPOINT.replace("https://", ""), "port": 443}],
    http_auth=(MASTER_USER, MASTER_PASSWORD),
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30,
    max_retries=3,
    retry_on_timeout=True,
)

    # Test it:
    indecies = client.cat.indices(format="json")
    for i in indecies[:1]:
        if i:
            print("Testing OpenSearch Connection:")
            print(f"Index: {i["index"]} \Status: {i["status"]} \nHealth: {i["health"]} \n  ")
            print("Success. Client created.")
            return client
        else:
            print("Client test Failed.")
            return False
        
    
# Deletes the index INDEX_NAME to get a clean slate
@safe_step
def wipe_os_index(client, INDEX_NAME):
    if client.indices.exists(INDEX_NAME):
        client.indices.delete(index=INDEX_NAME)
        print(f"[INFO] Deleted index {INDEX_NAME!r}")
    else:
        print(f"[ERROR] Index {INDEX_NAME} does not exist")


# Creates the new index INDEX_NAME
@safe_step
def create_os_index(client, INDEX_NAME):
    try:
        if not client.indices.exists(INDEX_NAME):
            print(f"[INFO] creating index {INDEX_NAME!r}\n")
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
                        # "chunk_text":   {"type": "text"},
                        # "chunk_index":  {"type": "integer"},
                        # "filename":     {"type": "keyword"},
                        "summary_text": {"type": "text"},
                        "participants": {"type": "keyword"},
                        # Prevent each URL_LINK_* key under `links` from creating new fields
                        "links": {
                            "type":   "object",
                            "dynamic": False
                        }
                    }
                }
            }
            client.indices.create(index=INDEX_NAME, body=mapping)
            print(f"[INFO] {INDEX_NAME} created.")
    except Exception as e:
        print(f"[ERROR] Creating index failed due to: {e}")


@safe_step
def actions_generator(DIRS_TO_INDEX, doc_limit=None):
    """
    Yields one document action at a time. Any error reading/parsing
    a file will be logged and that file skipped.
    """
    for directory in DIRS_TO_INDEX:
        this_limit = doc_limit if doc_limit is not None else len(os.listdir(directory))
        print(f"Pulling data from: '{directory}'")
        for filename in os.listdir(directory)[:this_limit]:
            if not filename.endswith(".json"):
                continue

            path = os.path.join(directory, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    doc = json.load(f)

                if not doc.get("date"):
                    doc.pop("date", None)
                yield {
                    "_index":  INDEX_NAME,
                    "_id":     doc.get("doc_id", filename),
                    "_source": doc
                }

            except Exception as e:
                print(f"[WARNING] Skipping file {filename!r} due to error: {e}")
                continue


# Reports on data before indexing it
@safe_step
def stream_summary(DIRS_TO_INDEX):
    total = 0
    for i in DIRS_TO_INDEX:
        size = len(os.listdir(i))
        print(f"   -> {size} docs in {i}")
        total += size
    print()
    print(f"[INFO] {total} documents ready to index.")
    return total


@safe_step
def stream_doc_to_os(client, doc_limit=None):
    """
    Streams every action from actions_generator into OpenSearch.
    Any BulkIndexError or unexpected exception on the whole stream
    is caught and logged; individual docs that fail are skipped.
    """
    total = stream_summary(DIRS_TO_INDEX)
    success = 0
    errors  = 0

    try:
        stream = helpers.streaming_bulk(
            client,
            actions_generator(DIRS_TO_INDEX, doc_limit=doc_limit),
            chunk_size=50,
            request_timeout=120,
            max_retries=2,
            initial_backoff=2,
            max_backoff=10,
            yield_ok=True,
            raise_on_error=False,    # yield failures rather than raise
        )

        for idx, (ok, result) in enumerate(stream):
            try:
                if ok:
                    success += 1
                else:
                    errors += 1
                    print(f"[WARNING] Bulk index failed for doc #{idx}: {result}")

            except Exception as inner_e:
                # Catch any unexpected error in our loop logic
                errors += 1
                print(f"[ERROR] Unexpected error processing result for doc #{idx}: {inner_e}")

            if (success + errors) % verbosity == 0:
                pct = round(success / total * 100, 1)
                print(f"  -> {success+errors}/{total} processed → {pct}% succeeded")

    except Exception as e:
        # Catch any failure in the bulk streaming itself
        print(f"[ERROR] Bulk streaming aborted due to unexpected error: {e}")

    print(f"[DONE ] Indexed {success}/{total} docs ({errors} skipped)")
    print("Refreshing index...")
    client.indices.refresh(index=INDEX_NAME)
    print("Index refreshed.")


# Post-indexing summery
@safe_step
def inspect_os_index(client, INDEX_NAME):
    # Searching the index w/ max 5 results
    resp = client.search(
        index=INDEX_NAME,
        body={
        "size": 0,
        "aggs": {
            "types": {
            "terms": { "field": "type", "size": 10 }
            }
        }
        }
    )

    print("Type buckets:")
    for bucket in resp["aggregations"]["types"]["buckets"]:
        print(f"  {bucket['key']}  → {bucket['doc_count']} docs")



def main():
    #---AUTHENTICATE TO OPENSEARCH
    client = create_os_client(OPENSEARCH_ENDPOINT, MASTER_USER, MASTER_PASSWORD)

    #---PREPARE FOR INDEXING
    wipe_os_index(client, INDEX_NAME)
    create_os_index(client, INDEX_NAME)
    stream_summary(DIRS_TO_INDEX)

    #---STREAM DATA TO OPENSEARCH
    stream_doc_to_os(client)

    #---REPORT ON COMPLETION
    inspect_os_index(client, INDEX_NAME)

