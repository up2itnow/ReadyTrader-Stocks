"""
Prometheus text-format exporter (Phase 4B).

This does NOT start an HTTP server by default. Instead, ReadyTrader exposes a tool that returns
the text format so operators can scrape it via sidecar, log collection, or periodic polling.
"""

from __future__ import annotations

import re
from typing import Any, Dict

_re_non_ident = re.compile(r"[^a-zA-Z0-9_]")


def _to_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if s and (s.isdigit() or (s.startswith("-") and s[1:].isdigit())):
            return int(s)
    return None


def _to_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None


def _name(s: str) -> str:
    s2 = _re_non_ident.sub("_", (s or "").strip())
    s2 = re.sub(r"_+", "_", s2)
    s2 = s2.strip("_")
    return s2.lower() or "unnamed"


def render_prometheus(snapshot: Dict[str, Any], *, namespace: str = "readytrader") -> str:
    """
    Render Metrics.snapshot() into Prometheus exposition format.
    """
    ns = _name(namespace)
    lines: list[str] = []

    uptime = snapshot.get("uptime_sec")
    if uptime is not None:
        lines.append(f"{ns}_uptime_sec {int(uptime)}")

    counters = snapshot.get("counters") or {}
    if isinstance(counters, dict):
        for k, v in sorted(counters.items(), key=lambda kv: str(kv[0])):
            iv = _to_int(v)
            if iv is None:
                continue
            lines.append(f"{ns}_counter_{_name(str(k))} {iv}")

    gauges = snapshot.get("gauges") or {}
    if isinstance(gauges, dict):
        for k, v in sorted(gauges.items(), key=lambda kv: str(kv[0])):
            fv = _to_float(v)
            if fv is None:
                continue
            lines.append(f"{ns}_gauge_{_name(str(k))} {fv}")

    timers = snapshot.get("timers") or {}
    if isinstance(timers, dict):
        for k, agg in sorted(timers.items(), key=lambda kv: str(kv[0])):
            if not isinstance(agg, dict):
                continue
            base = f"{ns}_timer_{_name(str(k))}"
            for field, suffix in (
                ("count", "count"),
                ("total_ms", "sum_ms"),
                ("max_ms", "max_ms"),
                ("avg_ms", "avg_ms"),
            ):
                if field not in agg:
                    continue
                fv = _to_float(agg[field])
                if fv is None:
                    continue
                lines.append(f"{base}_{suffix} {fv}")

    return "\n".join(lines) + "\n"

