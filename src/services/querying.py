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
from config import *
logger = logging.getLogger(__name__)


def create_os_client():
    client = OpenSearch(
        hosts=[{"host": OPENSEARCH_ENDPOINT, "port": 443}],
        http_auth=(MASTER_USER, MASTER_PASSWORD),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
        max_retries=5,
        retry_on_timeout=True
    )

    return client

def create_llm_client():
    return OpenAI(api_key=SECRET_KEY)

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
            model=EMBEDDINGS_MODEL,
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
            model=QUERY_MODEL,
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



def num_tokens_from_messages(messages, model: str=QUERY_MODEL) -> int:
    """
    Returns the total number of tokens that will be sent to the Chat API,
    counting both the message content *and* the per-message framing tokens.
    """
    encoding = tiktoken.encoding_for_model(model)
    # From OpenAI’s guidance:
    tokens_per_message = 4      # every message adds <im_start>, role, <im_end>
    tokens_per_name    = -1     # if you use the name field instead of role
    total_tokens = 0

    for m in messages:
        total_tokens += tokens_per_message
        for key, val in m.items():
            total_tokens += len(encoding.encode(val))
            if key == "name":
                total_tokens += tokens_per_name

    total_tokens += 2  # priming tokens for the assistant’s reply
    return total_tokens


class Memory:
    """
    Manages short, mid, and long term chat memory.
    """
    def __init__(
        self,
        llm_client: OpenAI,
        os_client,
        short_term_tokens: int = 1000,
        mid_term_turns: int = 5,
        memory_model: str = None,
        embeddings_model: str = None,
    ):
        self.llm = llm_client
        self.os = os_client
        self.memory_model = memory_model or MEMORY_MODEL
        self.embeddings_model = embeddings_model or EMBEDDINGS_MODEL

        self.turns = 0
        self.short_term: List[str] = []
        self.mid_term: str = ""
        self.long_term: List[Dict[str, Any]] = []

        self.short_term_tokens = short_term_tokens
        self.mid_term_turns = mid_term_turns
        self.long_term_index = f"memory_{datetime.utcnow():%Y%m%d_%H%M%S}"

        try:
            self.tokenizer = tiktoken.encoding_for_model(self.memory_model)
        except Exception:
            self.tokenizer = None

    def __repr__(self):
        return self.mid_term or ""

    def __str__(self):
        return self.mid_term or ""

    def add_turn(self) -> None:
        self.turns += 1

    def count_tokens(self, text: str) -> int:
        if not self.tokenizer:
            return len(text.split())
        return len(self.tokenizer.encode(text))

    def _extract_short(self, text: str) -> str:
        try:
            resp = self.llm.chat.completions.create(
                model=self.memory_model,
                messages=[
                    {"role": "system", "content": (
                        "You are a fact-extractor. From the text, list:\n"
                        "1. Persons mentioned, 2. Dates, 3. Numeric values, 4. Locations."
                    )},
                    {"role": "user", "content": text}
                ],
                temperature=0.0,
                max_tokens=self.short_term_tokens
            )
            return resp.choices[0].message.content
        except Exception:
            logger.exception("Short-term extraction failed")
            return text

    def _extract_mid(self, text: str) -> str:
        try:
            system_prompt = (
                "You are a memory-curation assistant. Merge the existing medium-term memory "
                "with the latest exchange, and output exactly in this format:\n---\n"
                "**Narrative Summary**\n<2–3 sentences>\n\n"
                "**Key Facts (JSON Array)**\n```json [ {\"Person\": \"...\"} ]```"
            )
            resp = self.llm.chat.completions.create(
                model=self.memory_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.0,
                max_tokens=1500
            )
            return resp.choices[0].message.content
        except Exception:
            logger.exception("Mid-term extraction failed")
            return self.mid_term or ""

    def _extract_long(self, text: str) -> List[Dict[str,Any]]:
        try:
            m = re.search(r"```json\s*(\[.*?\])\s*```", text, re.DOTALL)
            if not m:
                m = re.search(r"(\[.*\])", text, re.DOTALL)
            blob = m.group(1) if m else None
            if not blob:
                raise ValueError("No JSON blob found for facts")
            data = json.loads(blob)
            return data if isinstance(data, list) else [data]
        except Exception:
            logger.exception("Long-term parsing failed")
            return []

    def extract_facts(self, text: str, mode: str = "mid"):
        if mode == "short":
            return self._extract_short(text)
        if mode == "mid":
            return self._extract_mid(text)
        if mode == "long":
            return self._extract_long(text)
        raise ValueError(f"Unknown extract mode: {mode}")

    def short_term_memory(self, new_turn: str) -> List[str]:
        self.short_term.append(new_turn)
        total = sum(self.count_tokens(t) for t in self.short_term)
        while total > self.short_term_tokens and self.short_term:
            self.short_term.pop(0)
            total = sum(self.count_tokens(t) for t in self.short_term)
        return self.short_term

    def mid_term_memory(self) -> str:
        if not self.mid_term or self.turns % self.mid_term_turns == 0:
            joined = "\n".join(self.short_term)
            self.mid_term = self.extract_facts(joined, mode="mid")
        return self.mid_term

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _embed_text(self, client: AsyncOpenAI, text: str) -> List[float]:
        resp = await client.embeddings.create(
            model=self.embeddings_model,
            input=text
        )
        return resp.data[0].embedding

    async def long_term_memory(self) -> List[Dict[str,Any]]:
        if self.turns % self.mid_term_turns != 0:
            return self.long_term

        # (rebuild mid-term and extract facts as before) …
        facts = self.extract_facts(self.mid_term, mode="long")
        self.long_term = facts

        # ←―――――――――  HERE is where we create the index with the proper KNN mapping
        if not self.os.indices.exists(index=self.long_term_index):
            mapping = {
                "settings": {"index.knn": True},
                "mappings": {
                    "properties": {
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": 1536
                        }
                    }
                }
            }
            self.os.indices.create(index=self.long_term_index, body=mapping)

        emb_client = AsyncOpenAI(api_key=SECRET_KEY)
        sem = asyncio.Semaphore(10)
        tasks = [
            asyncio.create_task(self._process_and_index_fact(fact, emb_client, sem))
            for fact in facts
        ]
        await asyncio.gather(*tasks)
        return self.long_term

    async def _process_and_index_fact(self, fact: Dict[str,Any], client: AsyncOpenAI, sem: asyncio.Semaphore):
        async with sem:
            text = json.dumps(fact, ensure_ascii=False)
            try:
                vec = await self._embed_text(client, text)
                fact_doc = {**fact, "embedding": vec}
                doc_id = uuid.uuid4().hex
                self.os.index(
                    index=self.long_term_index,
                    id=doc_id,
                    body=fact_doc,
                    request_timeout=60
                )
            except Exception:
                logger.exception("Failed to embed/index fact")

    def retrieve_long_term_memory(self, query_emb: List[float], k: int = 5) -> List[Dict[str,Any]]:
        try:
            if not self.os.indices.exists(index=self.long_term_index):
                return []
            body = {"size": k, "query": {"knn": {"embedding": {"vector": query_emb, "k": k}}}}
            resp = self.os.search(index=self.long_term_index, body=body, request_timeout=30)
            
            results = []
            for hit in resp["hits"]["hits"]:
                doc = hit["_source"].copy()
                doc.pop("embedding", None)
                results.append(doc)

            return results
                
        except Exception:
            logger.exception("Long-term retrieval failed")
            return []

    def rebuild_memory(
        self,
        latest_prompt: str,
        latest_response: str,
        query_embedding: List[float]
    ) -> str:
        turn = f"User: {latest_prompt}\nAssistant: {latest_response}"
        short = self.short_term_memory(turn)
        mid = self.mid_term_memory()
        try:
            long_facts = self.retrieve_long_term_memory(query_embedding)
        except Exception:
            logger.exception("Error retrieving long-term memory")
            long_facts = []
        parts = ["\n".join(short), mid, json.dumps(long_facts, ensure_ascii=False)]
        return "\n\n".join(parts)


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
        "[answer_query] Turn %d | mem_summary=%r",
        memory.turns, mem_summary
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
                "Always provide information about the thread you draw information from (e.g. Date, From, To, or Subject) and do not refer to them as 'Thread'"
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

    # 7) Determine token usage, pick model, and reserve response budget
    # Exact token count (including per-message overhead)
    prompt_tokens = num_tokens_from_messages(system_msgs)

    # Minimum tokens we want for any substantive reply
    MIN_RESPONSE_TOKENS = 256

    # Context window limits (input + output)
    context_limits = {
        SMALL_QUERY_MODEL:        4_096,
        QUERY_MODEL:             16_384,
        LARGE_QUERY_MODEL:       32_768,
        ULTRA_LARGE_QUERY_MODEL: 128_000,
        SUMMARY_MODEL:         1_000_000,
    }
    # Completion (output) caps for each model
    completion_limits = {
        SMALL_QUERY_MODEL:         1_024,
        QUERY_MODEL:               4_096,
        LARGE_QUERY_MODEL:         8_192,
        ULTRA_LARGE_QUERY_MODEL:   16_384,
        SUMMARY_MODEL:           512_000,
    }

    # Decide which model can fit prompt + minimum reply
    required = prompt_tokens + MIN_RESPONSE_TOKENS
    if required <= context_limits[SMALL_QUERY_MODEL]:
        right_size_model = SMALL_QUERY_MODEL
    elif required <= context_limits[QUERY_MODEL]:
        right_size_model = QUERY_MODEL
    elif required <= context_limits[LARGE_QUERY_MODEL]:
        right_size_model = LARGE_QUERY_MODEL
    elif required <= context_limits[ULTRA_LARGE_QUERY_MODEL]:
        right_size_model = ULTRA_LARGE_QUERY_MODEL
    else:
        right_size_model = SUMMARY_MODEL

    logger.info(
        "[answer_query] prompt_tokens=%d | selected_model=%s",
        prompt_tokens, right_size_model
    )

    # Compute how many tokens remain in context for a reply
    model_context = context_limits[right_size_model]
    model_completion = completion_limits.get(right_size_model, model_context)
    available_context = model_context - prompt_tokens

    # Limit output to the lesser of available context or model's completion cap
    max_tokens_for_response = min(available_context, model_completion)
    # Ensure at least the minimum floor
    max_tokens_for_response = max(max_tokens_for_response, MIN_RESPONSE_TOKENS)

    # 8) Call the LLM
    logger.info(
        "[answer_query] Sending request to OpenAI model %s...",
        right_size_model
    )
    chat = llm_client.chat.completions.create(
        model=right_size_model,
        messages=system_msgs,
        temperature=0.2,
        max_tokens=max_tokens_for_response
    )
    response = chat.choices[0].message.content
    logger.info(
        "[ANSWER LENGTH] Received response char lenght(length=%d)",
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

    return system_msgs, response, merged_memory, retrieved_ids, query_embedding
