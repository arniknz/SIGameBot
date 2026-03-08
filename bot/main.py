import asyncio
import logging
import os
import signal

from dotenv import load_dotenv

import bot.base

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)


async def main() -> None:
    load_dotenv()
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise RuntimeError('BOT_TOKEN is not set in environment or .env file')

    new_bot = bot.base.Bot(token=token, concurrent_workers=3)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown(sig: signal.Signals) -> None:
        logger.info('Received %s, shutting down...', sig.name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    await new_bot.start()
    logger.info('Bot is running. Press Ctrl+C to stop.')
    await stop_event.wait()
    await new_bot.stop()


if __name__ == '__main__':
    asyncio.run(main())
