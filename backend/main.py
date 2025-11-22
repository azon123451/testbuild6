"""
Legacy entrypoint for hosting platforms that automatically run `python backend/main.py`.
It simply proxies to the bot's main loop.
"""

import asyncio

from bot.main import main as run_bot


def main():
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()

