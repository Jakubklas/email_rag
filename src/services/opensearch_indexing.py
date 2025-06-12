import os
import json
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
import boto3
from requests_aws4auth import AWS4Auth
from openai import OpenAI
from config import *


# Authenticates to OpenSearch
def create_os_client(OPENSEARCH_ENDPOINT, MASTER_USER, MASTER_PASSWORD):
    client = OpenSearch(
    hosts=[{"host": OPENSEARCH_ENDPOINT, "port": 443}],
    http_auth=(MASTER_USER, MASTER_PASSWORD),
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
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
def wipe_os_index(client, INDEX_NAME):
    if client.indices.exists(INDEX_NAME):
        client.indices.delete(index=INDEX_NAME)
        print(f"[INFO] Deleted index {INDEX_NAME!r}")
    else:
        print(f"[ERROR] Index {INDEX_NAME} does not exist")


# Creates the new index INDEX_NAME
def create_os_index(client, INDEX_NAME):
    try:
        if not client.indices.exists(INDEX_NAME):
            print(f"[INFO] creating index {INDEX_NAME!r}")
            print()
            mapping = {
                "settings": {"index": {"knn": True}},
                "mappings": {
                    "dynamic": True,
                    "properties": {
                        "doc_id":      {"type": "keyword"},
                        "thread_id":   {"type": "keyword"},
                        "message_id":  {"type": "keyword"},
                        "embedding":   {"type": "knn_vector", "dimension": 1536},
                        "type":        {"type": "keyword"},
                        "date":        {"type": "date"},
                        "subject":     {"type": "text"},
                        "chunk_text":  {"type": "text"},
                        "chunk_index": {"type": "integer"},
                        "filename":    {"type": "keyword"},
                        "summary_text":{"type": "text"},
                        "participants":{"type": "keyword"}
                    }
                }
            }
            client.indices.create(INDEX_NAME, body=mapping)
            print(f"[INFO] {INDEX_NAME} created.")
    except Exception as e:
        print(f"[ERROR] Creating index failed due to: {e}")


# Specifies indexing structure. Yields documents one by one for each file in each directory in DATDIRS_TO_INDEX
def actions_generator(DIRS_TO_INDEX):                      # Memory efficient index generator which loops over direcories
    for directory in DIRS_TO_INDEX:
        print(f"Pulling data from: '{directory}'")
        print()
        for filename in os.listdir(directory):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(directory, filename)
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)

            yield {
                "_index":  INDEX_NAME,
                "_id":     doc.get("doc_id", filename),
                "_source": doc
                }


# Reports on data before indexing it
def stream_summary(DIRS_TO_INDEX):
    total = 0
    for i in DIRS_TO_INDEX:
        size = len(os.listdir(i))
        print(f"   -> {size} docs in {i}")
        total += size
    print()
    print(f"[INFO] {total} documents ready to index.")
    return total


# Indexing workflow         #TODO: Make more robust before final indexing run to ensure no data was lost or skipped
def stream_doc_to_os(client):
    # First, report on the size
    total = stream_summary(DIRS_TO_INDEX)

    # Second, begin the indexing workflow
    success = 0
    for idx, (ok, result) in enumerate(
        helpers.streaming_bulk(
            client,
            actions_generator(DIRS_TO_INDEX),
            chunk_size=100,           # batches of 100
            request_timeout=60,       # 1 min time-out per request
            max_retries=2,
            initial_backoff=2,
            max_backoff=10,
            yield_ok=True             # uses a generator to drip-feed the data one-by-one
            )
        ):
        if ok:
            success += 1
        else:
            # result looks like {"index": {"_id": "...", "error": {...}}}
            print(f"[ERROR] Doc #{idx} failed to index:", result)

        if idx % verbosity == 0:
            print(f"  -> {idx}/{total} docs indexed -> {round(success/total*100, 0)}%")

    print(f"[DONE ] Finished indexing: {success}/{total} succeeded -> {round(success/total*100, 0)}%")

    print("Refreshing index...")
    client.indices.refresh(index=INDEX_NAME)

    print("Index refreshed.")


# Post-indexing summery
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


"""
── OPENSEARCH DATA STRUCTURE ──────────────────────────────────────────────────────────

{
  "settings": {
    "index": {
      "knn": true                                       // k-NN plugin enabled
    }
  },
  "mappings": {
    "dynamic": true,                                   // allow extra fields beyond those listed
    "properties": {
      "doc_id":       { "type": "keyword"        },
      "thread_id":    { "type": "keyword"        },
      "message_id":   { "type": "keyword"        },
      "embedding":    { "type": "knn_vector",
                        "dimension": 1536       },     // embedding vector field
      "type":         { "type": "keyword"        }, 
      "date":         { "type": "date"           },
      "subject":      { "type": "text"           },
      "chunk_text":   { "type": "text"           },
      "summary_text": { "type": "text"           },
      "chunk_index":  { "type": "integer"        },
      "filename":     { "type": "keyword"        },
      "participants": { "type": "keyword"        }
    }
  }
}
"""

"""
── OPENSEARCH EXAMPLE ──────────────────────────────────────────────────────────

{
  "_index": "email_rag",
  "_id":    "thread123-0",          // unique per chunk
  "_source": {
    "doc_id":      "XXXXXX",
    "type":        "email",
    "thread_id":   "thread123",
    "message_id":  "msg-abc-001",
    "date":        "2025-05-12T09:39:48Z",
    "subject":     "Re: Please book collection for Thursday",
    "participants":[
                    "alice@example.com",
                    "bob@example.com"
                   ],
    "chunk_index": 0,
    "chunk_text":  "Great, thank you!\n<END OF MESSAGE>",
    "embedding":   [ -0.02526, 0.01429, … ]  // length 1536
  }
}
"""