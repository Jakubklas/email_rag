import logging
import asyncio
import threading
from typing import List, Tuple
from src.utils.clients.llm_client import create_llm_client
from src.utils.clients.opensearch_client import create_os_client
from .search.knn_search import knn_search
from .search.query_rewriter import rewrite_query
from .memory.memory_manager import Memory
from .formatting.thread_formatter import format_threads
from .formatting.prompt_builder import build_system_messages, select_model_by_tokens
from config.config import *

logger = logging.getLogger(__name__)


class QueryService:
    """
    Main orchestrator for the query processing pipeline.
    Coordinates search, memory management, and response generation.
    """
    
    def __init__(self):
        self.llm_client = create_llm_client()
        self.os_client = create_os_client()
        self.memory = Memory(self.llm_client, self.os_client)
    
    def answer_query(
        self,
        query_text: str,
        retrieved_ids: List[str] = None
    ) -> Tuple[str, str, str, List[str], List[float]]:
        """
        Process a query and return a comprehensive response.
        """
        # 1) New turn & mid-term
        self.memory.add_turn()
        mem_summary = self.memory.mid_term_memory() if self.memory.turns > 1 else ""
        last_snip = self.memory.short_term[-1] if self.memory.short_term else ""
        logger.info("")
        logger.info("")
        logger.info("[USER QUERY]: %s", query_text)
        logger.info("")
        logger.info(
            "[answer_query] Turn %d | mem_summary=%r | last_snip=%r",
            self.memory.turns, mem_summary, last_snip
        )

        # 2) Query rewriting
        adjusted_query = rewrite_query(query_text, mem_summary, self.llm_client)
        logger.info("[answer_query] Rewritten query: %r", adjusted_query)

        # 3) Retrieval from OpenSearch
        logger.info(
            "[answer_query] Calling knn_search with retrieved_ids=%s",
            retrieved_ids or []
        )
        hits, retrieved_ids, query_embedding = knn_search(
            query_text=adjusted_query,
            llm_client=self.llm_client,
            os_client=self.os_client,
            retrieved_ids=retrieved_ids or []
        )
        logger.info(
            "[answer_query] knn_search returned %d hits | new retrieved_ids=%s",
            len(hits), retrieved_ids
        )

        # 4) Format threads
        thread_blocks = format_threads(hits, EMAILS_INDEX, self.os_client)
        logger.info(
            "[answer_query] Formatted thread_blocks length: %d",
            len(thread_blocks)
        )

        # 5) Long-term memory retrieval
        long_facts = self.memory.retrieve_long_term_memory(query_embedding)
        logger.info(
            "[answer_query] Retrieved long-term facts count: %d",
            len(long_facts)
        )

        # 6) Build the system+user messages
        system_msgs = build_system_messages(query_text, mem_summary, long_facts, thread_blocks)
        logger.info(
            "[answer_query] Built system_msgs with %d messages",
            len(system_msgs)
        )

        # 7) Select model and get response
        selected_model = select_model_by_tokens(system_msgs)
        logger.info(
            "[answer_query] Selected model: %s",
            selected_model
        )

        # 8) Call the LLM
        logger.info(
            "[answer_query] Sending request to OpenAI model %s...",
            selected_model
        )
        chat = self.llm_client.chat.completions.create(
            model=selected_model,
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
        self.memory.short_term_memory(f"User: {query_text}\nAssistant: {response}")
        self.memory.mid_term_memory()
        logger.info("[answer_query] Updated short-term and mid-term memory")

        # 10) Async long-term memory
        def run_long_term_memory():
            asyncio.run(self.memory.long_term_memory())
        threading.Thread(target=run_long_term_memory).start()
        logger.info("[answer_query] Launched background long-term memory update")

        # 11) Rebuild combined memory for next turn
        merged_memory = self.memory.rebuild_memory(
            latest_prompt=query_text,
            latest_response=response,
            query_embedding=query_embedding
        )
        logger.info("[answer_query] Completed and returning results")

        prompt = "\n\n".join(m["content"] for m in system_msgs)
        return prompt, response, merged_memory, retrieved_ids, query_embedding


def answer_query(
    query_text: str,
    retrieved_ids: List[str] = None,
    memory: Memory = None
) -> Tuple[str, str, str, List[str], List[float]]:
    """
    Legacy function wrapper for backward compatibility.
    """
    service = QueryService()
    if memory:
        service.memory = memory
    return service.answer_query(query_text, retrieved_ids)