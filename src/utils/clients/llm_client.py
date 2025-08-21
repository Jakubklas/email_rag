from openai import OpenAI

from src.utils.safe_step import safe_step
from config.config import *


@safe_step
def create_llm_client():
    """
    Creates OpenAI client using API key stored as
    an env variable.
    """
    return OpenAI(api_key=SECRET_KEY)