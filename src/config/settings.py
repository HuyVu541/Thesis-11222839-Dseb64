"""
Application settings and configuration.

All configuration is centralized here and loaded from environment variables.
Settings are validated using Pydantic for type safety.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Dict, Any, Optional, List, Literal
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # ============================================
    # API Configuration
    # ============================================
    
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: List[str] = ["http://localhost:3001", "http://localhost:5173"]
    
    # ============================================
    # LLM Configuration
    # ============================================
    
    llm_provider: Literal["google-generativeai", "openai"] = "google-generativeai"
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.7
    llm_top_p: float = 0.95
    llm_top_k: int = 20
    
    llm_config: Dict[str, Any] = {
        "provider": "google-generativeai",
        "model": "gemini-2.5-flash"
    }
    
    # ============================================
    # Database Configuration
    # ============================================
    
    database_url: str = "postgresql://user:password@postgres:5432/langgraph"
    
    # ============================================
    # Memory Configuration
    # ============================================
    
    memory_base_path: str = "memory"
    memory_mode: Literal["rag", "sam"] = "sam"  # sam = structural, rag = vector store
    
    # ============================================
    # Langfuse (Tracing) Configuration
    # ============================================
    
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    langfuse_enabled: bool = True  # Set to False to disable tracing
    
    # ============================================
    # Logging Configuration
    # ============================================
    
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Sync LLM config
        self.llm_config = {
            "provider": self.llm_provider,
            "model": self.llm_model,
            "temperature": self.llm_temperature,
            "top_p": self.llm_top_p,
            "top_k": self.llm_top_k,
        }


# Global settings instance
settings = Settings()