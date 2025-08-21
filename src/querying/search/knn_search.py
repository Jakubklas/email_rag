import time
import logging
from typing import List, Tuple
from opensearchpy.exceptions import TransportError, ConnectionError as OSCxnError
from openai import OpenAIError
from config.config import *

logger = logging.getLogger(__name__)


def knn_search(
    query_text: str,
    llm_client,
    os_client,
    retrieved_ids: List[str] = None,
    size: int = 5,
    retries: int = 5,
    backoff: int = 2
) -> Tuple[List, List[str], List[float]]:
    """
    Perform vector similarity search against OpenSearch.
    Returns hits, retrieved_ids, and query embedding.
    """
    retrieved_ids = retrieved_ids or []

    # 1) Embed the query
    try:
        q_vec = llm_client.embeddings.create(
            model=EMB_MODEL,
            input=query_text
        ).data[0].embedding
    except OpenAIError as e:
        logger.error(f"[knn_search] Embedding failed: {e}")
        return [], [], []

    # 2) Build k-NN query with filters
    knn_body = {
        "timeout": "60s",
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

    # 3) Execute with retries & backoff
    attempt = 0
    while attempt < retries:
        try:
            resp = os_client.search(
                index=THREADS_INDEX,
                body=knn_body,
                request_timeout=60
            )
            hits = resp.get("hits", {}).get("hits", [])
            ids = [h["_id"] for h in hits]
            return hits, ids, q_vec

        except (TransportError, OSCxnError) as e:
            logger.warning(f"[knn_search] attempt {attempt+1} failed: {e}")
            time.sleep(backoff ** attempt)
            attempt += 1

    logger.error("[knn_search] Failed after multiple attempts.")
    return [], [], []