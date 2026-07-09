#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def fail(message: str) -> int:
    print(f"[rollout-waves] {message}")
    return 1


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def validate(path: Path) -> int:
    if not path.exists():
        return fail(f"plan file not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return fail(f"unable to read JSON: {exc}")

    if not isinstance(payload, dict):
        return fail("plan root must be an object")

    waves = payload.get("waves")
    if not isinstance(waves, list) or len(waves) < 2:
        return fail("plan must define at least 2 rollout waves")

    previous_percent = -1
    for idx, wave in enumerate(waves, start=1):
        if not isinstance(wave, dict):
            return fail(f"wave {idx} must be an object")

        name = wave.get("name")
        if not isinstance(name, str) or not name.strip():
            return fail(f"wave {idx} must include non-empty name")

        percent = _as_int(wave.get("maxTrafficPercent"))
        if percent is None or percent < 1 or percent > 100:
            return fail(f"wave {idx} maxTrafficPercent must be integer in [1,100]")

        if percent <= previous_percent:
            return fail(f"wave {idx} maxTrafficPercent must be strictly increasing")
        previous_percent = percent

        soak_minutes = _as_int(wave.get("soakMinutes"))
        if soak_minutes is None or soak_minutes < 0:
            return fail(f"wave {idx} soakMinutes must be integer >= 0")

        criteria = wave.get("promotionCriteria")
        if not isinstance(criteria, dict):
            return fail(f"wave {idx} promotionCriteria must be an object")

        error_threshold = criteria.get("errorRateThreshold")
        if not isinstance(error_threshold, (int, float)) or error_threshold < 0 or error_threshold > 1:
            return fail(f"wave {idx} errorRateThreshold must be number in [0,1]")

        p95_latency = _as_int(criteria.get("maxP95LatencyMs"))
        if p95_latency is None or p95_latency < 1:
            return fail(f"wave {idx} maxP95LatencyMs must be integer >= 1")

        minimum_requests = _as_int(criteria.get("minimumRequests"))
        if minimum_requests is None or minimum_requests < 1:
            return fail(f"wave {idx} minimumRequests must be integer >= 1")

    if waves[0]["maxTrafficPercent"] > 10:
        return fail("first wave must be canary-like (<=10% maxTrafficPercent)")

    if waves[-1]["maxTrafficPercent"] != 100:
        return fail("final wave must end at 100% traffic")

    print(f"[rollout-waves] validated {len(waves)} waves from {path}")
    return 0


def main() -> int:
    raw_path = sys.argv[1] if len(sys.argv) > 1 else "docs/release-rollout-waves.json"
    return validate(Path(raw_path))


if __name__ == "__main__":
    raise SystemExit(main())
