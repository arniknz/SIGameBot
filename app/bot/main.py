import asyncio
import logging
import logging.handlers
import os
import signal

import bot.base
import config
import nlp.openrouter


def setup_logging(cfg: config.Config) -> None:
    root = logging.getLogger()
    root.setLevel(cfg.log_level)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    log_dir = os.path.dirname(cfg.log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        cfg.log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


logger = logging.getLogger(__name__)


async def main() -> None:
    cfg = config.Config.from_env()
    setup_logging(cfg)

    new_bot = bot.base.Bot(cfg)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown(sig: signal.Signals) -> None:
        logger.info(
            "Received %s — initiating graceful shutdown",
            sig.name,
        )
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    if not cfg.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY must be set in environment")
    nlp.openrouter.set_openrouter_client(
        nlp.openrouter.OpenRouterClient(
            api_key=cfg.openrouter_api_key,
            model=cfg.openrouter_model,
        )
    )
    await new_bot.start()
    logger.info("Bot is running. Press Ctrl+C to stop.")
    await stop_event.wait()
    await new_bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
