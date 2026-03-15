from __future__ import annotations

import dataclasses
import os

import dotenv


@dataclasses.dataclass
class Config:
    bot_token: str

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "sigamebot"
    db_user: str = "postgres"
    db_password: str = "postgres"

    workers_count: int = 3
    question_selection_timeout: int = 30
    buzzer_timeout: int = 10
    answer_timeout: int = 15
    max_failed_selections: int = 3

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"

    log_level: str = "INFO"
    log_file: str = "logs/bot.log"

    admin_username: str = "admin"
    admin_password: str = "admin"
    admin_api_port: int = 8000

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def rabbitmq_url(self) -> str:
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/"
        )

    @classmethod
    def from_env(cls, env_path: str | None = None) -> Config:
        dotenv.load_dotenv(env_path)

        bot_token = os.getenv("BOT_TOKEN", "")
        if not bot_token:
            raise RuntimeError("BOT_TOKEN is not set in environment or .env")

        return cls(
            bot_token=bot_token,
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_name=os.getenv("DB_NAME", "sigamebot"),
            db_user=os.getenv("DB_USER", "postgres"),
            db_password=os.getenv("DB_PASSWORD", "postgres"),
            workers_count=int(os.getenv("WORKERS_COUNT", "3")),
            question_selection_timeout=int(
                os.getenv("QUESTION_SELECTION_TIMEOUT", "30")
            ),
            buzzer_timeout=int(os.getenv("BUZZER_TIMEOUT", "10")),
            answer_timeout=int(os.getenv("ANSWER_TIMEOUT", "15")),
            max_failed_selections=int(
                os.getenv("MAX_FAILED_SELECTIONS", "3")
            ),
            rabbitmq_host=os.getenv("RABBITMQ_HOST", "localhost"),
            rabbitmq_port=int(os.getenv("RABBITMQ_PORT", "5672")),
            rabbitmq_user=os.getenv("RABBITMQ_USER", "guest"),
            rabbitmq_password=os.getenv("RABBITMQ_PASSWORD", "guest"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", "logs/bot.log"),
            admin_username=os.getenv("ADMIN_USERNAME", "admin"),
            admin_password=os.getenv("ADMIN_PASSWORD", "admin"),
            admin_api_port=int(os.getenv("ADMIN_API_PORT", "8000")),
        )
