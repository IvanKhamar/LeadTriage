"""Settings from environment variables (like IOptions<T> bound to configuration in .NET)."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": .env also holds n8n's variables, which the app does not use.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Empty tokens reject every call (fail closed), so a missing .env never opens an endpoint.
    webhook_token: SecretStr = SecretStr("")
    enrich_token: SecretStr = SecretStr("")
    source_token_verde_kitchen: SecretStr = SecretStr("")

    n8n_webhook_url: str = "http://localhost:5678/webhook/leads"
    # Connect timeout is short (n8n is next door); the read timeout covers the whole workflow,
    # the LLM call and its retries included.
    forward_connect_timeout_s: float = 3.0
    forward_read_timeout_s: float = 60.0

    rate_limit_per_minute: int = 5
    max_body_bytes: int = 16 * 1024

    data_dir: Path = Path("data")

    # USD per million tokens. LLM_* = Claude (LLM_MODE=claude); GEMINI_* = Gemini, 0 on the free tier.
    llm_price_input_per_mtok: float = 0.10
    llm_price_output_per_mtok: float = 0.50
    gemini_price_input_per_mtok: float = 0.0
    gemini_price_output_per_mtok: float = 0.0

    def prices(self, provider: str) -> tuple[float, float]:
        """(input, output) USD per million tokens for the provider that answered."""
        if provider == "gemini":
            return self.gemini_price_input_per_mtok, self.gemini_price_output_per_mtok
        if provider == "mock":
            return 0.0, 0.0
        return self.llm_price_input_per_mtok, self.llm_price_output_per_mtok

    def source_tokens(self) -> dict[str, SecretStr]:
        """Known server-to-server sources and their tokens. A new source = a new setting + a line here."""
        return {"verde-kitchen": self.source_token_verde_kitchen}
