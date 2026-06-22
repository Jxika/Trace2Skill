"""Simple append-only text logger."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class SimpleLog:
    """Append messages to a .txt file (UTF-8)."""

    def __init__(self, log_file: str | Path) -> None:
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self.log_file.open("a", encoding="utf-8")

    def write(self, message: str) -> None:
        """Write one line to the log file."""
        self._fp.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")
        self._fp.flush()

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None

    def __enter__(self) -> SimpleLog:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
