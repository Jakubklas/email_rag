import time
import logging
from typing import List, Tuple
from opensearchpy.exceptions import TransportError, ConnectionError as OSCxnError
from openai import OpenAIError
from config.config import *

logger = logging.getLogger(__name__)


def knn_search(query_text, llm_client, os_client, retrieved_ids=None, size=5, retries=5, backoff=2):
    """
    Queries OpenSearch using KNN to get top 5 semantically.
    similar threads to user's query. Returns hits, retrieved_ids,
    and query_embedding
    """
    retrieved_ids = retrieved_ids or []

    # Get query embeddings
    try:
        q_vec = llm_client.embeddings.create(model=EMB_MODEL, input=query_text).data[0].embedding
    except OpenAIError as e:
        logger.error(f"[knn_search] Embedding failed: {e}")
        return [], [], []

    # Get the threads from OpenSearch based on the embeddings
    knn_body = {
        "timeout": "30s",
        "size": size,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"type": "thread"}},
                    {"bool": {"must_not": {"ids": {"values": retrieved_ids}}}}
                ],
                "must": {
                    "knn": {
                        "embedding": {
                            "vector": q_vec,
                            "k": size,
                            "method_parameters": {"ef_search": size * 10}
                        }
                    }
                }
            }
        }
    }

    # Execute with retries
    attempt = 0
    while attempt < retries:
        try:
            resp = os_client.search(index=THREADS_INDEX, body=knn_body, request_timeout=30)
            hits = resp.get("hits", {}).get("hits", [])
            ids = [h["_id"] for h in hits]
            return hits, ids, q_vec

        except Exception as e:
            logger.warning(f"[knn_search] attempt {attempt+1} failed: {e}")
            time.sleep(backoff ** attempt)
            attempt += 1

    logger.error(f"[knn_search] Failed after {attempt} attempts.")
    return [], [], []