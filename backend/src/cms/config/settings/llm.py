"""Model providers and tracing: OpenAI, OpenRouter and LangSmith."""

from pydantic import BaseModel


class LLMSettings(BaseModel):
    # --- OpenAI ---
    openai_api_key: str
    openai_model_main: str = "gpt-6-luna"
    openai_model_cheap: str = "gpt-6-luna"

    # --- OpenRouter ---
    openrouter_model_main: str = "openai/gpt-6-luna"
    openrouter_model_cheap: str = "openai/gpt-6-luna"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    open_router_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_rerank_model: str = "voyageai/rerank-2.5-lite"
    openrouter_timeout_seconds: float = 30.0

    # --- LangSmith tracing ---
    langsmith_tracing: bool = True
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str
    langsmith_project: str = "complaint-cms"
