"""Application settings, loaded from environment / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./venturemind.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # RAG / ChromaDB
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "startups"

    # LLM Provider: "ollama", "gemini", or "auto" (default: "auto")
    llm_provider: str = "auto"

    # Ollama local LLM configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout: float = 120.0

    # Google Gemini configuration
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Groq configuration
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # OpenRouter configuration
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # LLM Fallback order: comma-separated list of providers to try (e.g. "openrouter,gemini,groq,ollama")
    llm_fallback_order: str = "openrouter,gemini,groq,ollama"

    # External Research & Tool APIs
    tavily_api_key: str = ""
    serper_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        configured = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        defaults = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"]
        return list(dict.fromkeys(configured + defaults))


settings = Settings()
