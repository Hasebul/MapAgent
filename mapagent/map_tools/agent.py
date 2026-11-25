"""The Map-Tool Agent (Section 3.4): the inner-layer agent of the Map Service module.

Given the query (and, for visual questions, the place and radius found by the Visual Place Recognizer), the
agent selects MapTools through function calling. All tool calls requested in one turn are executed in parallel;
if the agent asks for more tools after seeing the results, they are executed in a further round, which supports
sequential flows such as "nearby search, then details of the candidates". The agent does not answer the question:
it returns the retrieved data, which the Map Service module passes on to the next modules.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..llm import LLMClient
from ..prompts import MAP_AGENT_SYSTEM_PROMPT
from .client import MapsClient
from .tools import TOOL_SCHEMAS, canonical_tool_name, run_map_tool


@dataclass
class MapAgentResult:
    information: str
    calls: List[Dict[str, Any]] = field(default_factory=list)
    rounds: int = 0
    final_message: str = ""


class MapToolAgent:
    def __init__(
        self,
        llm: LLMClient,
        model: str,
        maps: MapsClient,
        *,
        max_rounds: int = 3,
        max_workers: int = 5,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        verbose: bool = False,
    ) -> None:
        self.llm = llm
        self.model = model
        self.maps = maps
        self.max_rounds = max(1, int(max_rounds))
        self.max_workers = max(1, int(max_workers))
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.verbose = verbose

    def run(self, query: str, visual_context: Optional[str] = None) -> MapAgentResult:
        user_content = query if not visual_context else f"{query}\n\n{visual_context}"
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": MAP_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        calls: List[Dict[str, Any]] = []
        outputs: List[str] = []
        cache: Dict[Tuple[str, str], str] = {}
        final_message = ""
        rounds = 0

        for rounds in range(1, self.max_rounds + 1):
            response = self.llm.chat(
                self.model,
                messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=TOOL_SCHEMAS,
            )
            if not response.tool_calls:
                final_message = response.content
                break
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content or None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.function.name, "arguments": call.function.arguments or "{}"},
                        }
                        for call in response.tool_calls
                    ],
                }
            )
            results = self._execute(response.tool_calls, cache)
            for call, (name, arguments, output, repeated) in zip(response.tool_calls, results):
                messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
                calls.append({"round": rounds, "tool": name, "arguments": arguments, "output": output})
                if not repeated:
                    outputs.append(output)
                if self.verbose:
                    print(f"[map-tool agent] round {rounds}: {name}({arguments})")

        return MapAgentResult(
            information="\n\n".join(out.strip() for out in outputs if out and out.strip()),
            calls=calls,
            rounds=rounds,
            final_message=final_message,
        )

    def _execute(self, tool_calls: List[Any], cache: Dict[Tuple[str, str], str]) -> List[Tuple[str, Any, str, bool]]:
        """Run the tool calls of one turn in parallel; identical calls are executed only once."""
        prepared = []
        for call in tool_calls:
            name = canonical_tool_name(call.function.name)
            raw = call.function.arguments or "{}"
            try:
                arguments = json.loads(raw)
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                prepared.append((name, raw, None, f"Error: could not parse the arguments of {name}: {exc}"))
                continue
            key = (name, json.dumps(arguments, sort_keys=True, ensure_ascii=False))
            prepared.append((name, arguments, key, None))

        pending = {}
        for name, arguments, key, error in prepared:
            if key is not None and key not in cache and key not in pending:
                pending[key] = (name, arguments)
        if pending:
            workers = min(self.max_workers, len(pending))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    key: pool.submit(run_map_tool, self.maps, name, arguments) for key, (name, arguments) in pending.items()
                }
                fresh = {key: future.result() for key, future in futures.items()}
        else:
            fresh = {}

        results = []
        emitted = set()
        for name, arguments, key, error in prepared:
            if error is not None:
                results.append((name, arguments, error, False))
                continue
            if key in fresh and key not in emitted:
                output, repeated = fresh[key], False
                cache[key] = output
                emitted.add(key)
            else:
                output, repeated = cache.get(key) or fresh.get(key, ""), True
            results.append((name, arguments, output, repeated))
        return results
