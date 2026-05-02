"""
LLM Manager — initializes and returns a LangChain chat model.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any, List
import os
from loguru import logger


class LLMManager:
    """
    Manages LLM initialization for different providers.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def _get_api_key(self, provider: str) -> str:
        if self.config.get('api_key'):
            return self.config['api_key']
        if provider == "google-generativeai":
            key = os.getenv("GOOGLE_API_KEY")
        elif provider == "openai":
            key = os.getenv("OPENAI_API_KEY")
        else:
            key = os.getenv(f"{provider.upper()}_API_KEY")
        if not key:
            raise ValueError(f"API key not found for provider {provider}.")
        return key

    def get_callbacks(self) -> List[Any]:
        """Return tracing callbacks (Langfuse if configured)."""
        try:
            from ..config.settings import settings
            if (settings.langfuse_enabled
                and settings.langfuse_public_key
                and settings.langfuse_secret_key):
                # Langfuse v3: must initialize the global client first
                import langfuse
                langfuse.Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
                
                from langfuse.langchain import CallbackHandler
                handler = CallbackHandler(
                    public_key=settings.langfuse_public_key,
                )
                return [handler]
        except Exception as e:
            logger.warning(f"Langfuse callback init failed: {e}")
        return []

    def get_llm(self):
        provider = self.config['provider']
        api_key = self._get_api_key(provider)

        if provider == "google-generativeai":
            llm = ChatGoogleGenerativeAI(
                model=self.config['model'],
                google_api_key=api_key,
                temperature=self.config.get('temperature', 0.7),
                top_p=self.config.get('top_p', 0.95),
                top_k=self.config.get('top_k', 20),
                max_retries=3,
            )
        else:
            from langchain.chat_models import init_chat_model
            config_with_key = {**self.config, "api_key": api_key}
            llm = init_chat_model(**config_with_key)

        return llm