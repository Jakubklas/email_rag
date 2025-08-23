import json
import tiktoken
from config.config import *


def build_system_messages(query_text, mem_summary, long_facts, thread_blocks):
    """
    Builds model system messages in a system + user style.
    Contains the main system prompt.
    """
    # System prompt
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
                "Answer with a high degree of detail, citing your sources, numbers, facts, or examples."
                "Weave the insights in naturally, but do not quote it back verbatim."
                "If the answer isn't in the context, admit you don't know and offer to look it up."
            )
        }
    ]
    
    # User query 
    system_msgs.append({"role": "user", "content": f"Answer this query from Redcoat Express: {query_text}"})
    
    # Add memory summary if any
    if mem_summary:
        system_msgs.append({"role": "system", "content": f"[Conversation Summary]\n{mem_summary}"})
    
    # Add facts from a vector store if any
    if long_facts:
        system_msgs.append({
            "role": "system",
            "content": f"[Long-Term Memory Facts]\n{json.dumps(long_facts, ensure_ascii=False, indent=2)}\n\n"
        })

    # Add the actual emails as formatted threads
    if thread_blocks:
        system_msgs.append({"role": "system", "content": f"[Relevant Email Threads]\n{thread_blocks}"})
    
    return system_msgs


def select_model_by_tokens(system_msgs):
    """
    Select the right-size model based on the token count.
    Generally used for chat queries.
    """
    # Get the size query incl. system prompt & retrieved emails
    prompt = "\n\n".join(msg["content"] for msg in system_msgs)
    enc = tiktoken.encoding_for_model(MEDIUM_MODEL)
    prompt_tokens = len(enc.encode(prompt))
    
    # Return the right size model (string name)
    if prompt_tokens <= 4000:
        return SMALL_MODEL
    elif prompt_tokens <= 16000:
        return MEDIUM_MODEL
    elif prompt_tokens <= 32000:
        return LARGE_MODEL
    else:
        return VERY_LARGE_MODEL