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
    Main orchestrator for user query processing. Takes care of knn
    search, memory management, and response generation.
    """

    def __init__(self):
        self.llm_client = create_llm_client()
        self.os_client = create_os_client()
        self.memory = Memory(self.llm_client, self.os_client)
    
    def answer_query(self, query_text, retrieved_ids=None):
        """
        Takes a query and returns a comprehensive response.
        """
        # Add a turn to memory & summarize if needed
        self.memory.add_turn()
        mem_summary = self.memory.mid_term_memory() if self.memory.turns > 1 else ""
        last_snip = self.memory.short_term[-1] if self.memory.short_term else ""
    
        logger.info("")
        logger.info(f"[USER QUERY]: {query_text}")
        logger.info("")
        logger.info(f"[answer_query] Turn %d | mem_summary={self.memory.turns} | last_snip={last_snip}")

        # Optimize user's prompt
        adjusted_query = rewrite_query(query_text, mem_summary, self.llm_client)
        logger.info(f"[answer_query] Rewritten query: {adjusted_query}")

        # Query OpenSearch for relevent threads
        logger.info(f"[answer_query] Calling knn_search with retrieved_ids={retrieved_ids or []}")
        hits, retrieved_ids, query_embedding = knn_search(
            query_text=adjusted_query,
            llm_client=self.llm_client,
            os_client=self.os_client,
            retrieved_ids=retrieved_ids or []
        )
        logger.info(f"[answer_query] knn_search returned {len(hits)} hits | new retrieved_ids={retrieved_ids}")

        # Reconstruct back the full threads based on the thread_id 
        thread_blocks = format_threads(hits, EMAILS_INDEX, self.os_client)
        logger.info(f"[answer_query] Formatted thread_blocks length: {len(thread_blocks)}")

        # Retrieve known facts from conversation memory if any
        long_facts = self.memory.retrieve_long_term_memory(query_embedding)
        logger.info(f"[answer_query] Retrieved long-term facts count: {len(long_facts)}")

        # Format everything as a system prompt
        system_msgs = build_system_messages(query_text, mem_summary, long_facts, thread_blocks)
        logger.info(f"[answer_query] Built system_msgs with {len(system_msgs)} messages")

        # Select the right size model
        picked_model = select_model_by_tokens(system_msgs)
        logger.info(f"[answer_query] Selected model: {picked_model}")

        # Call the LLM
        logger.info(f"[answer_query] Sending request to OpenAI model {picked_model}")
        chat = self.llm_client.chat.completions.create(
            model=picked_model,
            messages=system_msgs,
            temperature=0.2
        )
        response = chat.choices[0].message.content
        logger.info(f"[answer_query] Model response length = {len(response)} chars",)
        logger.info(f"[ANSWER]: {response}")
        logger.info("")

        # Update short/mid/long-term conversation memory
        self.memory.short_term_memory(f"User: {query_text}\nAssistant: {response}")
        self.memory.mid_term_memory()
        logger.info("[answer_query] Updated short-term and mid-term memory")

        # Async update long-term memory in the background
        def run_long_term_memory():
            asyncio.run(self.memory.long_term_memory())
        threading.Thread(target=run_long_term_memory).start()
        logger.info("[answer_query] Launched background long-term memory update")

        # Rebuild memory for next turn
        complete_memory = self.memory.rebuild_memory(
            latest_prompt=query_text,
            latest_response=response,
            query_embedding=query_embedding
        )

        # Return the LLM response
        logger.info("[answer_query] Completed and returning results")
        prompt = "\n\n".join(m["content"] for m in system_msgs)

        return prompt, response, complete_memory, retrieved_ids, query_embedding