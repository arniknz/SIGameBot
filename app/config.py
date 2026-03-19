from __future__ import annotations

import os
from dataclasses import dataclass

import dotenv
import game.constants


@dataclass
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

    answer_similarity_threshold: float = (
        game.constants.ANSWER_SIMILARITY_THRESHOLD_DEFAULT
    )
    answer_fuzzy_ratio_min: float = game.constants.ANSWER_FUZZY_RATIO_DEFAULT
    sentence_transformer_model: str = (
        game.constants.SENTENCE_TRANSFORMER_MODEL_DEFAULT
    )
    embedding_service_url: str = ""
    max_question_word_overlap: float = (
        game.constants.MAX_QUESTION_WORD_OVERLAP_DEFAULT
    )
    max_question_similarity: float = (
        game.constants.MAX_QUESTION_SIMILARITY_DEFAULT
    )
    min_answer_similarity: float = game.constants.MIN_ANSWER_SIMILARITY_DEFAULT

    lobby_timeout: int = game.constants.LOBBY_TIMEOUT_DEFAULT
    enable_phonetic: bool = game.constants.ENABLE_PHONETIC_DEFAULT
    phonetic_threshold: float = game.constants.PHONETIC_THRESHOLD_DEFAULT
    max_csv_rows: int = game.constants.MAX_CSV_ROWS_DEFAULT
    embedding_cache_size: int = game.constants.EMBEDDING_CACHE_SIZE_DEFAULT
    use_fp16: bool = game.constants.USE_FP16_DEFAULT

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
            max_failed_selections=int(os.getenv("MAX_FAILED_SELECTIONS", "3")),
            rabbitmq_host=os.getenv("RABBITMQ_HOST", "localhost"),
            rabbitmq_port=int(os.getenv("RABBITMQ_PORT", "5672")),
            rabbitmq_user=os.getenv("RABBITMQ_USER", "guest"),
            rabbitmq_password=os.getenv("RABBITMQ_PASSWORD", "guest"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", "logs/bot.log"),
            admin_username=os.getenv("ADMIN_USERNAME", "admin"),
            admin_password=os.getenv("ADMIN_PASSWORD", "admin"),
            admin_api_port=int(os.getenv("ADMIN_API_PORT", "8000")),
            answer_similarity_threshold=float(
                os.getenv(
                    game.constants.ENV_ANSWER_SIMILARITY_THRESHOLD,
                    str(game.constants.ANSWER_SIMILARITY_THRESHOLD_DEFAULT),
                )
            ),
            sentence_transformer_model=os.getenv(
                game.constants.ENV_SENTENCE_TRANSFORMER_MODEL,
                game.constants.SENTENCE_TRANSFORMER_MODEL_DEFAULT,
            ),
            embedding_service_url=os.getenv("EMBEDDING_SERVICE_URL", ""),
            answer_fuzzy_ratio_min=float(
                os.getenv(
                    game.constants.ENV_ANSWER_FUZZY_RATIO,
                    str(game.constants.ANSWER_FUZZY_RATIO_DEFAULT),
                )
            ),
            max_question_word_overlap=float(
                os.getenv(
                    game.constants.ENV_MAX_QUESTION_WORD_OVERLAP,
                    str(game.constants.MAX_QUESTION_WORD_OVERLAP_DEFAULT),
                )
            ),
            max_question_similarity=float(
                os.getenv(
                    game.constants.ENV_MAX_QUESTION_SIMILARITY,
                    str(game.constants.MAX_QUESTION_SIMILARITY_DEFAULT),
                )
            ),
            min_answer_similarity=float(
                os.getenv(
                    game.constants.ENV_MIN_ANSWER_SIMILARITY,
                    str(game.constants.MIN_ANSWER_SIMILARITY_DEFAULT),
                )
            ),
            lobby_timeout=int(
                os.getenv(
                    game.constants.ENV_LOBBY_TIMEOUT,
                    str(game.constants.LOBBY_TIMEOUT_DEFAULT),
                )
            ),
            enable_phonetic=os.getenv(
                game.constants.ENV_ENABLE_PHONETIC, "true"
            ).lower()
            in ("true", "1", "yes"),
            phonetic_threshold=float(
                os.getenv(
                    game.constants.ENV_PHONETIC_THRESHOLD,
                    str(game.constants.PHONETIC_THRESHOLD_DEFAULT),
                )
            ),
            max_csv_rows=int(
                os.getenv(
                    game.constants.ENV_MAX_CSV_ROWS,
                    str(game.constants.MAX_CSV_ROWS_DEFAULT),
                )
            ),
            embedding_cache_size=int(
                os.getenv(
                    game.constants.ENV_EMBEDDING_CACHE_SIZE,
                    str(game.constants.EMBEDDING_CACHE_SIZE_DEFAULT),
                )
            ),
            use_fp16=os.getenv(game.constants.ENV_USE_FP16, "true").lower()
            in ("true", "1", "yes"),
        )
