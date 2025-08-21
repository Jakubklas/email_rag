import json
import tiktoken
from typing import List, Dict, Any, Tuple
from config.config import *


def construct_prompt(query_text: str, memory: str, retrieved_ids: List[str], thread_blocks: str) -> Tuple[str, List[str], None]:
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
    prompt = f"{context}{query_text}{thread_blocks}"

    return prompt, retrieved_ids, None


def build_system_messages(
    query_text: str,
    mem_summary: str,
    long_facts: List[Dict[str, Any]],
    thread_blocks: str
) -> List[Dict[str, str]]:
    """
    Build the system+user messages for LLM completion.
    """
    system_msgs = [
        {
            "role": "system",
            "content": (
                "You are a detail-oriented, helpful assistant for Redcoat Express Ltd.\n"
                "You have access to three pieces of context:\n"
                "  • A concise summary of our past conversation\n"
                "  • The long-term known facts\n"
                "  • The full text of relevant email threads retrieved for this query\n\n"
                "When answering, always draw on all of that context if it helps."
                "Answer with a high degree of detail citing your sources, numbers, facts, or examples."
                "Weave the insights in naturally, but do not quote it back verbatim."
                "If the answer isn't in the context, admit you don't know and offer to look it up."
            )
        }
    ]
    system_msgs.append({"role": "user", "content": f"Answer this query from Redcoat Express Ltd: {query_text}"})
    if mem_summary:
        system_msgs.append({"role": "system", "content": f"[Conversation Summary]\n{mem_summary}"})
    if long_facts:
        system_msgs.append({
            "role": "system",
            "content": f"[Long-Term Memory Facts]\n{json.dumps(long_facts, ensure_ascii=False, indent=2)}\n\n"
        })
    if thread_blocks:
        system_msgs.append({"role": "system", "content": f"[Relevant Email Threads]\n{thread_blocks}"})
    
    return system_msgs


def select_model_by_tokens(system_msgs: List[Dict[str, str]]) -> str:
    """
    Select appropriate model based on prompt token count.
    """
    prompt = "\n\n".join(m["content"] for m in system_msgs)
    enc = tiktoken.encoding_for_model(MEDIUM_MODEL)
    prompt_tokens = len(enc.encode(prompt))
    
    if prompt_tokens <= 4000:
        return SMALL_MODEL
    elif prompt_tokens <= 16000:
        return MEDIUM_MODEL
    else:
        return VERY_LARGE_MODEL