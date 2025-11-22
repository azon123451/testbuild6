import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    token: str
    operator_secret: str
    data_dir: Path
    operators_allowlist: List[int]

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN is missing. Provide a bot token via environment variables."
            )

        secret = os.getenv("OPERATOR_SECRET", "changeme")
        data_dir = Path(os.getenv("DATA_DIR", "data")).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)

        allowlist_raw = os.getenv("OPERATORS_ALLOWLIST", "")
        allowlist: List[int] = []
        for chunk in allowlist_raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                allowlist.append(int(chunk))
            except ValueError:
                raise RuntimeError(
                    f"OPERATORS_ALLOWLIST must contain integers, got: {chunk}"
                ) from None

        return cls(
            token=token,
            operator_secret=secret,
            data_dir=data_dir,
            operators_allowlist=allowlist,
        )


settings = Settings.from_env()


__all__ = ["settings"]

