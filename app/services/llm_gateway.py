from openai import AsyncOpenAI
from app.core.config import settings

class LLMGateway:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.llm_base_url,  # This tells it to go to OpenRouter
            api_key=settings.anthropic_api_key,
        )