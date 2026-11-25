"""Per-query resource accounting.

These counters correspond to the cost metrics of Section 6 / Appendix D of the paper:
number of LLM API calls, token consumption, Google Maps usage and execution time.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass


@dataclass
class UsageStats:
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    map_tool_calls: int = 0  # invocations of a MapTool (Trip / Route / Nearby / PlaceInfo)
    map_api_calls: int = 0  # raw Google Maps web-service requests made by those tools

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict:
        data = asdict(self)
        data["total_tokens"] = self.total_tokens
        return data


class UsageTracker:
    """Thread-safe counters shared by the LLM client and the Google Maps client."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats = UsageStats()

    def reset(self) -> None:
        with self._lock:
            self._stats = UsageStats()

    def snapshot(self) -> UsageStats:
        with self._lock:
            return UsageStats(**asdict(self._stats))

    def add_llm_call(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        with self._lock:
            self._stats.llm_calls += 1
            self._stats.prompt_tokens += int(prompt_tokens or 0)
            self._stats.completion_tokens += int(completion_tokens or 0)

    def add_map_tool_call(self, count: int = 1) -> None:
        with self._lock:
            self._stats.map_tool_calls += count

    def add_map_api_call(self, count: int = 1) -> None:
        with self._lock:
            self._stats.map_api_calls += count
