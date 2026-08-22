from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    bot_token: str = ""
    admin_password: str = ""
    redis_url: str = "redis://localhost:6379/0"
    db_path: str = "data/support.db"
    log_level: str = "INFO"
    sla_reply_minutes: int = 30
    sla_close_hours: int = 24
    sentry_dsn: str = ""
    metrics_port: int = 8084

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            bot_token=os.getenv("BOT_TOKEN", ""),
            admin_password=os.getenv("ADMIN_PASSWORD", ""),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            db_path=os.getenv("DB_PATH", "data/support.db"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            sla_reply_minutes=int(os.getenv("SLA_REPLY_MINUTES", "30")),
            sla_close_hours=int(os.getenv("SLA_CLOSE_HOURS", "24")),
            sentry_dsn=os.getenv("SENTRY_DSN", ""),
            metrics_port=int(os.getenv("METRICS_PORT", "8084")),
        )


@dataclass
class State:
    config: Config = field(default_factory=Config.from_env)
