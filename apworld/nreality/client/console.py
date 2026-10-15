"""Message log for the web page: server prints as coloured segments plus the client's own log lines."""
import collections
import copy
import logging
import re
import time
from typing import Any

from NetUtils import JSONtoTextParser

ANSI = re.compile(r"\x1b\[[0-9;]*m")
INPUT_COLOR = "#" + JSONtoTextParser.color_codes["orange"]


class SegmentParser(JSONtoTextParser):
    """Resolves PrintJSON parts like the text client, but returns {text, color} segments instead of ANSI."""

    def __call__(self, parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.handle_node(part) for part in copy.deepcopy(parts)]

    def _handle_text(self, node):
        return dict(text=node.get("text", ""), color=None)

    def _handle_color(self, node):
        codes = [code for code in node["color"].split(";") if code in self.color_codes]
        return dict(text=node.get("text", ""), color="#" + self.color_codes[codes[-1]] if codes else None)


class WebConsole(logging.Handler):
    def __init__(self, ctx, size: int = 500) -> None:
        super().__init__(logging.INFO)
        self.ctx = ctx
        self.parser = SegmentParser(ctx)
        self.entries: collections.deque[dict[str, Any]] = collections.deque(maxlen=size)
        self.last_id = 0

    def add(self, parts: list[dict[str, Any]], kind: str, relevant: bool = True) -> None:
        self.last_id += 1
        self.entries.append(dict(id=self.last_id, time=time.time(), kind=kind, relevant=relevant, parts=parts))

    def add_text(self, text: str, kind: str, color: str | None = None) -> None:
        self.add([dict(text=ANSI.sub("", text), color=color)], kind)

    def add_print_json(self, args: dict[str, Any]) -> None:
        # Item finds between other players are hidden on the page unless the user asks for them.
        self.add(self.parser(args["data"]), args.get("type", "") or "server",
                 relevant=not self.ctx.is_uninteresting_item_send(args))

    def since(self, after: int) -> list[dict[str, Any]]:
        return [entry for entry in self.entries if entry["id"] > after]

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.add_text(record.getMessage(), "error" if record.levelno >= logging.ERROR else "client")
        except Exception:
            self.handleError(record)
