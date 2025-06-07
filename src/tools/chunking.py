from config import *
import tiktoken

def chunk_text(text, encoder = ENCODER_NAME, token_window=MAX_TOKENS, overlap=OVERLAP):
    """
    Splits raw text into chunks of X tokens with Y tokens overlap.
    """
    encoder = tiktoken.get_encoding(encoder)
    tokens = encoder.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + token_window, len(tokens))
        chunk_tok = tokens[start:end]
        chunks.append(encoder.decode(chunk_tok))
        start += token_window - overlap
    return chunks
