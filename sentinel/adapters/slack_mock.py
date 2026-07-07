"""Mock Slack adapter that records 'posted' messages instead of sending them."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class PostedMessage:
    channel: str
    text: str
    ts: str


class MockSlackAdapter:
    """Captures posted messages in-memory and echoes them to stdout."""

    def __init__(self, echo: bool = True) -> None:
        self.echo = echo
        self.messages: list[PostedMessage] = []

    def post_message(self, channel: str, text: str) -> str:
        ts = f"{time.time():.6f}"
        self.messages.append(PostedMessage(channel=channel, text=text, ts=ts))
        if self.echo:
            print(f"\n[slack:{channel}] posted message {ts}\n{text}\n")
        return ts
