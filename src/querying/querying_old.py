import os
import json
import logging
import time
from typing import List, Union, Dict, Any
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from opensearchpy.exceptions import TransportError, ConnectionError as OSCxnError
from tenacity import retry, stop_after_attempt, wait_exponential
from requests_aws4auth import AWS4Auth
from openai import OpenAI, OpenAIError, AsyncOpenAI
from typing import List, Tuple
import tiktoken
import re
import uuid

from datetime import datetime
from random import random
import asyncio
import threading
from config.config import *
from src.utils.semantic_memory import SemanticMemory
from src.utils.clients import create_llm_client, create_os_client
logger = logging.getLogger(__name__)


llm_client = create_llm_client()
os_client = create_os_client()

def knn_search(
    query_text,
    retrieved_ids=None,
    llm_client=llm_client,
    os_client=os_client,
    size=5,
    retries=5,
    backoff=2
):
    retrieved_ids = retrieved_ids or []

    # 1) Embed the query
    try:
        q_vec = llm_client.embeddings.create(
            model=EMB_MODEL,
            input=query_text
        ).data[0].embedding
    except OpenAIError as e:
        logging.error(f"[knn_search] Embedding failed: {e}")
        return [], [], []

    # 2) Build a single k-NN + filter query
    knn_body = {
        "timeout": "60s",
        "size": size,
        "query": {
            "bool": {
                # filter out non-thread types and already-retrieved IDs
                "filter": [
                    {"term": {"type": "thread"}},
                    {"bool": {"must_not": {"ids": {"values": retrieved_ids}}}}
                ],
                # then run k-NN over exactly that subset
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
            logging.warning(f"[knn_search] attempt {attempt+1} failed: {e}")
            time.sleep(backoff ** attempt)
            attempt += 1

    logging.error("[knn_search] Failed after multiple attempts.")
    return [], [], []


def reconstruct_thread(index_name, thread_id, max_msgs=1000, os_client=os_client):
    """
    Fetches every full email (with inlined attachments) for a given thread_id,
    sorted by date, and returns a list of header+body strings.
    """
    resp = os_client.search(
        index=index_name,
        body={
            "size": max_msgs,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"thread_id": thread_id}}
                    ]
                }
            },
            "sort": [{"date": {"order": "asc"}}]
        }
    )

    messages = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        headers = (
            f"\n\nFrom: {src.get('from')}"
            f"\nTo:   {src.get('to')}"
            f"\nCC:   {src.get('cc')}"
            f"\nDate: {src.get('date')}"
            f"\nSubject: {src.get('subject')}\n\n"
        )
        # `body` now contains original email + all attachment texts
        messages.append(headers + src.get("body", ""))
    return messages


def construct_prompt(query_text, memory, retrieved_ids, thread_blocks):
    """
    Builds the user-visible prompt by concatenating:
      - Optional mid-term summary
      - The new user query
      - The pre-formatted thread blocks
    """
    # 1) Memory prefix (if available)
    if memory:
        context = f"Summary of the most recent conversation: {memory}\n\n"
    else:
        context = ""

    # 2) Assemble prompt parts
    # thread_blocks is assumed to be a single string containing all "---- Thread Number X ----" sections
    prompt = f"{context}{query_text}{thread_blocks}"

    return prompt, retrieved_ids, None


def format_threads(hits: List[Dict[str, Any]], index_name: str) -> str:
    """
    Given the raw hits from knn_search, reconstruct each thread and join them.
    """
    blocks = []
    for idx, hit in enumerate(hits, start=1):
        summary = hit["_source"].get("summary_text")
        thread_id = hit["_source"].get("thread_id")
        header = (
            f"\n\n---- Thread Number {idx} ----\n"
            f"Summary: {summary}\n\n"
        )
        body = "".join(reconstruct_thread(index_name, thread_id))
        blocks.append(header + body)
    return "".join(blocks)


def rewrite_query(raw_query: str, mem_summary: str) -> str:
    """
    If the user’s query is a pronoun-heavy follow-up, 
    expand it using the mid-term memory summary.
    """
    # Only fire when it looks like a follow-up
    if True: # raw_query.lower().startswith(("what about", "and", "also", "how about")):
        resp = llm_client.chat.completions.create(
            model=MEDIUM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a query-rewriter.  Rewrite the user’s follow-up question as it relates to"
                        "the conversation summary. Write a short, standalone question optimized for semantic search retrieval."
                    )
                },
                {"role": "system", "content": f"[Conversation Summary]\n{mem_summary or ""}"},
                {"role": "user", "content": raw_query}
            ],
            temperature=0.0,
            max_tokens=64
        )
        return resp.choices[0].message.content.strip()
    else:
        return raw_query



import logging

# Configure root logger once in your application entry-point:
logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more verbosity
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

def answer_query(
    query_text: str,
    retrieved_ids: List[str] = None,
    memory: Memory = None
) -> Tuple[str, str, str, List[str], List[float]]:
    # 1) New turn & mid-term
    memory.add_turn()
    mem_summary = memory.mid_term_memory() if memory.turns > 1 else ""
    last_snip  = memory.short_term[-1] if memory.short_term else ""
    logger.info("")  # preserve blank line
    logger.info("")
    logger.info("[USER QUERY]: %s", query_text)
    logger.info("")
    logger.info(
        "[answer_query] Turn %d | mem_summary=%r | last_snip=%r",
        memory.turns, mem_summary, last_snip
    )

    # 2) Query rewriting
    adjusted_query = rewrite_query(query_text, mem_summary)
    logger.info("[answer_query] Rewritten query: %r", adjusted_query)

    # 3) Retrieval from OpenSearch
    logger.info(
        "[answer_query] Calling knn_search with retrieved_ids=%s",
        retrieved_ids or []
    )
    hits, retrieved_ids, query_embedding = knn_search(
        query_text=adjusted_query,
        retrieved_ids=retrieved_ids or []
    )
    logger.info(
        "[answer_query] knn_search returned %d hits | new retrieved_ids=%s",
        len(hits), retrieved_ids
    )

    # 4) Format threads
    thread_blocks = format_threads(hits, EMAILS_INDEX)
    logger.info(
        "[answer_query] Formatted thread_blocks length: %d",
        len(thread_blocks)
    )

    # 5) Long-term memory retrieval
    long_facts = memory.retrieve_long_term_memory(query_embedding)
    logger.info(
        "[answer_query] Retrieved long-term facts count: %d",
        len(long_facts)
    )

    # 6) Build the system+user messages
    system_msgs = [
        {
            "role":"system",
            "content":(
                "You are a detail-oriented, helpful assistant for Redcoat Express Ltd.\n"
                "You have access to three pieces of context:\n"
                "  • A concise summary of our past conversation\n"
                "  • The long-term known facts\n"
                "  • The full text of relevant email threads retrieved for this query\n\n"
                "When answering, always draw on all of that context if it helps."
                "Answer with a high degree of detail citing your sources, numbers, facts, or examples."
                "Weave the insights in naturally, but do not quote it back verbatim."
                "If the answer isn’t in the context, admit you don’t know and offer to look it up."
            )
        }
    ]
    system_msgs.append({"role":"user", "content": f"Answer this query from Redcoat Express Ltd: {query_text}"})
    if mem_summary:
        system_msgs.append({"role":"system", "content":f"[Conversation Summary]\n{mem_summary}"})
    if long_facts:
        system_msgs.append({
            "role":"system",
            "content": f"[Long-Term Memory Facts]\n{json.dumps(long_facts, ensure_ascii=False, indent=2)}\n\n"
        })
    if thread_blocks:
        system_msgs.append({"role":"system", "content":f"[Relevant Email Threads]\n{thread_blocks}"})
    logger.info(
        "[answer_query] Built system_msgs with %d messages",
        len(system_msgs)
    )

    # 7) Construct prompt
    prompt = "\n\n".join(m["content"] for m in system_msgs)
    enc = tiktoken.encoding_for_model(MEDIUM_MODEL)
    prompt_tokens = len(enc.encode(prompt))
    if prompt_tokens <= 4000:
        right_size_model = SMALL_MODEL
    elif prompt_tokens <= 16000:
        right_size_model = MEDIUM_MODEL
    else:
        right_size_model = VERY_LARGE_MODEL
    logger.info(
        "[answer_query] Prompt tokens=%d | selected_model=%s",
        prompt_tokens, right_size_model
    )

    # 8) Call the LLM
    logger.info(
        "[answer_query] Sending request to OpenAI model %s...",
        right_size_model
    )
    chat = llm_client.chat.completions.create(
        model=right_size_model,
        messages=system_msgs,
        temperature=0.2
    )
    response = chat.choices[0].message.content
    logger.info(
        "[answer_query] Received response (length=%d)",
        len(response)
    )
    logger.info("[ANSWER]: %s", response)
    logger.info("")

    # 9) Update memories
    memory.short_term_memory(f"User: {query_text}\nAssistant: {response}")
    memory.mid_term_memory()
    logger.info("[answer_query] Updated short-term and mid-term memory")

    # 10) Async long-term memory
    def run_long_term_memory():
        asyncio.run(memory.long_term_memory())
    threading.Thread(target=run_long_term_memory).start()
    logger.info("[answer_query] Launched background long-term memory update")

    # 11) Rebuild combined memory for next turn
    merged_memory = memory.rebuild_memory(
        latest_prompt=query_text,
        latest_response=response,
        query_embedding=query_embedding
    )
    logger.info("[answer_query] Completed and returning results")

    return prompt, response, merged_memory, retrieved_ids, query_embedding


def main():
    """
    Test function for querying functionality.
    """
    test_query = "What are the main topics discussed in recent emails?"
    print(f"Testing query: {test_query}")
    
    try:
        result = answer_query(test_query)
        print(f"Query result: {result[1]}")  # response is at index 1
        return result
    except Exception as e:
        print(f"Query failed: {e}")
        return None


if __name__ == "__main__":
    main()
