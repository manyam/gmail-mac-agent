import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class LLMConfig:
    provider: str
    model: str
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    timeout_seconds: int = 45


@dataclass
class GmailConfig:
    labels: List[str] = field(default_factory=lambda: ["INBOX"])
    additional_query: str = "-category:promotions -category:social -category:spam"
    lookback_hours: int = 24
    max_threads: int = 35
    credentials_path: Path = field(
        default_factory=lambda: Path(os.path.expanduser("~/.gmail_agent/credentials.json"))
    )
    token_path: Path = field(
        default_factory=lambda: Path(os.path.expanduser("~/.gmail_agent/token.json"))
    )
    state_db_path: Path = field(
        default_factory=lambda: Path(os.path.expanduser("~/.gmail_agent/state.db"))
    )


@dataclass
class NotificationConfig:
    enabled: bool = True
    sound: str = "Glass"


@dataclass
class OutputConfig:
    daily_briefs_dir: Path = field(
        default_factory=lambda: Path(os.path.expanduser("~/Documents/GmailDailyBriefs"))
    )
    notification: NotificationConfig = field(default_factory=NotificationConfig)


@dataclass
class AgentConfig:
    gmail: GmailConfig = field(default_factory=GmailConfig)
    llm_primary: LLMConfig = field(
        default_factory=lambda: LLMConfig(
            provider="ollama",
            model="gemma4:26b-mlx",
            base_url="http://localhost:11434",
            timeout_seconds=60,
        )
    )
    llm_backup: LLMConfig = field(
        default_factory=lambda: LLMConfig(
            provider="gemini",
            model="gemini-3.8-flash",
            api_key_env="GOOGLE_API_KEY",
            timeout_seconds=30,
        )
    )
    output: OutputConfig = field(default_factory=OutputConfig)


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """Load configuration from YAML file or return defaults."""
    if not config_path:
        base_dir = Path(__file__).resolve().parent.parent
        default_locations = [
            base_dir / "config.yaml",
            Path("config.yaml"),
            Path("gmail_agent/config.yaml"),
            Path(os.path.expanduser("~/.gmail_agent/config.yaml")),
        ]
        for loc in default_locations:
            if loc.exists():
                config_path = str(loc)
                break

    if not config_path or not os.path.exists(config_path):
        return AgentConfig()

    if not yaml:
        return AgentConfig()

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    gmail_data = data.get("gmail", {})
    gmail_cfg = GmailConfig(
        labels=gmail_data.get("labels", ["INBOX"]),
        additional_query=gmail_data.get(
            "additional_query", "-category:promotions -category:social -category:spam"
        ),
        lookback_hours=gmail_data.get("lookback_hours", 24),
        max_threads=gmail_data.get("max_threads", 35),
        credentials_path=Path(
            os.path.expanduser(gmail_data.get("credentials_path", "~/.gmail_agent/credentials.json"))
        ),
        token_path=Path(
            os.path.expanduser(gmail_data.get("token_path", "~/.gmail_agent/token.json"))
        ),
        state_db_path=Path(
            os.path.expanduser(gmail_data.get("state_db_path", "~/.gmail_agent/state.db"))
        ),
    )

    llm_data = data.get("llm", {})
    primary_data = llm_data.get("primary", {})
    primary_cfg = LLMConfig(
        provider=primary_data.get("provider", "ollama"),
        base_url=primary_data.get("base_url", "http://localhost:11434"),
        model=primary_data.get("model", "gemma4:26b-mlx"),
        timeout_seconds=primary_data.get("timeout_seconds", 60),
    )

    backup_data = llm_data.get("backup", {})
    backup_cfg = LLMConfig(
        provider=backup_data.get("provider", "gemini"),
        model=backup_data.get("model", "gemini-3.8-flash"),
        api_key_env=backup_data.get("api_key_env", "GOOGLE_API_KEY"),
        timeout_seconds=backup_data.get("timeout_seconds", 30),
    )

    output_data = data.get("output", {})
    notif_data = output_data.get("notification", {})
    output_cfg = OutputConfig(
        daily_briefs_dir=Path(
            os.path.expanduser(
                output_data.get("daily_briefs_dir", "~/Documents/GmailDailyBriefs")
            )
        ),
        notification=NotificationConfig(
            enabled=notif_data.get("enabled", True),
            sound=notif_data.get("sound", "Glass"),
        ),
    )

    return AgentConfig(
        gmail=gmail_cfg,
        llm_primary=primary_cfg,
        llm_backup=backup_cfg,
        output=output_cfg,
    )
