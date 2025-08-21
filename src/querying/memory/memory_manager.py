import json
import uuid
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
import tiktoken
from openai import OpenAI, AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from config.config import *

logger = logging.getLogger(__name__)


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
        self.embeddings_model = embeddings_model or EMB_MODEL

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
            import re
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

        facts = self.extract_facts(self.mid_term, mode="long")
        self.long_term = facts

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