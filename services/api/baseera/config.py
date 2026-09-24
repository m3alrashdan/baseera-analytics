from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    artifact_root: Path
    environment: str = "development"
    session_hours: int = 12
    upload_max_bytes: int = 25 * 1024 * 1024
    allowed_origins: tuple[str, ...] = ("http://localhost:3000",)
    llm_base_url: str | None = None
    llm_provider: str = "disabled"
    llm_model: str = "qwen3.5:9b"
    llm_timeout_seconds: float = 180
    llm_context_tokens: int = 4096
    llm_output_tokens: int = 384
    llm_threads: int = 6
    login_rate_limit: int = 10
    api_rate_limit: int = 120
    rate_limit_window_seconds: int = 60
    connector_allow_hosts: tuple[str, ...] = ()
    connector_private_hosts: tuple[str, ...] = ()
    connector_postgres_sslmode: str = "verify-full"
    connector_max_rows: int = 10_000
    # AI analyst team. "auto" uses Claude when an Anthropic key is configured, then a
    # configured local Ollama model, then the deterministic expert engine.
    agent_provider: str = "auto"
    anthropic_api_key: str | None = field(default=None, repr=False)
    anthropic_model: str = "claude-opus-5"
    anthropic_effort: str = "high"
    anthropic_fallbacks: bool = True
    anthropic_timeout_seconds: float = 300
    agent_max_tool_calls: int = 12
    agent_inline: bool = False

    @property
    def secure_cookies(self) -> bool:
        return self.environment not in {"development", "test"}


def load_settings() -> Settings:
    origins = tuple(
        item.strip()
        for item in os.getenv("BASEERA_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if item.strip()
    )
    hosts = tuple(
        item.strip().lower()
        for item in os.getenv("BASEERA_CONNECTOR_ALLOW_HOSTS", "").split(",")
        if item.strip()
    )
    # An on-premise deployment reaches sources on the customer's own private network. Those
    # hosts must be named explicitly here so the adapter's anti-SSRF default stays in force
    # for every address an operator has not approved.
    private_hosts = tuple(
        item.strip().lower()
        for item in os.getenv("BASEERA_CONNECTOR_PRIVATE_HOSTS", "").split(",")
        if item.strip()
    )
    return Settings(
        database_url=os.getenv(
            "BASEERA_DATABASE_URL", "sqlite:///./.baseera/baseera-development.db"
        ),
        artifact_root=Path(os.getenv("BASEERA_ARTIFACT_ROOT", "./.baseera/artifacts")),
        environment=os.getenv("BASEERA_ENVIRONMENT", "development"),
        session_hours=int(os.getenv("BASEERA_SESSION_HOURS", "12")),
        upload_max_bytes=int(os.getenv("BASEERA_UPLOAD_MAX_BYTES", str(25 * 1024 * 1024))),
        allowed_origins=origins,
        llm_base_url=os.getenv("BASEERA_LLM_BASE_URL") or None,
        llm_provider=os.getenv("BASEERA_LLM_PROVIDER", "disabled").lower(),
        llm_model=os.getenv("BASEERA_LLM_MODEL", "qwen3.5:9b"),
        llm_timeout_seconds=float(os.getenv("BASEERA_LLM_TIMEOUT_SECONDS", "180")),
        llm_context_tokens=int(os.getenv("BASEERA_LLM_CONTEXT_TOKENS", "4096")),
        llm_output_tokens=int(os.getenv("BASEERA_LLM_OUTPUT_TOKENS", "384")),
        llm_threads=int(os.getenv("BASEERA_LLM_THREADS", "6")),
        login_rate_limit=int(os.getenv("BASEERA_LOGIN_RATE_LIMIT", "10")),
        api_rate_limit=int(os.getenv("BASEERA_API_RATE_LIMIT", "120")),
        rate_limit_window_seconds=int(os.getenv("BASEERA_RATE_LIMIT_WINDOW_SECONDS", "60")),
        connector_allow_hosts=hosts,
        connector_private_hosts=private_hosts,
        connector_postgres_sslmode=os.getenv("BASEERA_CONNECTOR_POSTGRES_SSLMODE", "verify-full"),
        connector_max_rows=int(os.getenv("BASEERA_CONNECTOR_MAX_ROWS", "10000")),
        agent_provider=os.getenv("BASEERA_AGENT_PROVIDER", "auto").lower(),
        anthropic_api_key=os.getenv("BASEERA_ANTHROPIC_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or None,
        anthropic_model=os.getenv("BASEERA_ANTHROPIC_MODEL", "claude-opus-5"),
        anthropic_effort=os.getenv("BASEERA_ANTHROPIC_EFFORT", "high").lower(),
        anthropic_fallbacks=os.getenv("BASEERA_ANTHROPIC_FALLBACKS", "default").lower()
        not in {"off", "false", "0", "none"},
        anthropic_timeout_seconds=float(os.getenv("BASEERA_ANTHROPIC_TIMEOUT_SECONDS", "300")),
        agent_max_tool_calls=int(os.getenv("BASEERA_AGENT_MAX_TOOL_CALLS", "12")),
        agent_inline=os.getenv("BASEERA_AGENT_INLINE", "").lower() in {"1", "true", "yes"},
    )
