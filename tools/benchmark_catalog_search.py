"""Benchmark the native catalog query path with synthetic long-name libraries."""

from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from collections import OrderedDict
from dataclasses import replace
from types import SimpleNamespace

from crosshair_overlay.crosshairs.catalog import build_builtin_catalog
from crosshair_overlay.ui.bridge_router import BridgeCommandRouter


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def library_of_size(size: int) -> OrderedDict:
    seed = list(build_builtin_catalog().values())
    definitions = OrderedDict()
    for index in range(size):
        original = seed[index % len(seed)]
        style = replace(original.style,
                        style_id=f"generated-{index:05d}",
                        display_name=f"Long synthetic precision micro reticle variant {index:05d} " + ("detail " * 8))
        item = replace(original, style=style,
                       aliases=("micro sight" if index % 10 == 0 else "long geometric pattern",))
        definitions[item.style_id] = item
    return definitions


def main() -> None:
    result = []
    for count in (100, 1000, 10000):
        definitions = library_of_size(count)
        window = SimpleNamespace(
            _definitions=definitions,
            _style_payload=lambda definition: {"id": definition.style_id},
            _library_collections=[],
            _library_tags={},
            _recent_style_ids=[],
        )
        router = BridgeCommandRouter(window)
        payload = {"query": "micro sight", "filter": "all", "page": 0, "pageSize": 36}
        cold_started = time.perf_counter()
        router.dispatch("queryCatalog", payload)
        cold_query_ms = (time.perf_counter() - cold_started) * 1000
        durations = []
        for _ in range(50):
            started = time.perf_counter()
            response = router.dispatch("queryCatalog", payload)
            durations.append((time.perf_counter() - started) * 1000)
        tracemalloc.start()
        baseline_current, _ = tracemalloc.get_traced_memory()
        router.dispatch("queryCatalog", payload)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result.append({
            "definitions": count,
            "query": payload["query"],
            "page_size": 36,
            "matches": response["total"],
            "cold_search_ms": round(cold_query_ms, 3),
            "search_ms_p50": round(percentile(durations, 0.50), 3),
            "search_ms_p95": round(percentile(durations, 0.95), 3),
            "search_ms_mean": round(statistics.mean(durations), 3),
            "peak_temporary_bytes": max(0, peak - baseline_current),
            "repeats": len(durations),
            "scope": "native query handler only; excludes WebChannel, React rendering, first paint, and memory held by the library",
        })
    print(json.dumps({"results": result}, indent=2))


if __name__ == "__main__":
    main()
