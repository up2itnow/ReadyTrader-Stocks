"""
Generate `docs/TOOLS.md` from the authoritative tool definitions in `server.py`.

Usage:
  python tools/generate_tool_docs.py

This avoids documentation drift as MCP tools evolve.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server.py"
OUT = ROOT / "docs" / "TOOLS.md"


def _is_mcp_tool_decorator(dec: ast.AST) -> bool:
    return (
        isinstance(dec, ast.Call)
        and isinstance(dec.func, ast.Attribute)
        and isinstance(dec.func.value, ast.Name)
        and dec.func.value.id == "mcp"
        and dec.func.attr == "tool"
    )


def _format_default(expr: ast.AST) -> str:
    """
    Render a default value for display in docs.

    We prefer a safe, readable representation:
    - try literal_eval for simple literals
    - fallback to source snippet if available
    """
    try:
        v = ast.literal_eval(expr)
        if isinstance(v, str):
            return repr(v)
        return str(v)
    except Exception:
        return "…"


def _signature(fn: ast.FunctionDef) -> str:
    args = fn.args
    parts: list[str] = []

    # positional-only args (rare in this repo)
    for a in args.posonlyargs:
        parts.append(a.arg)
    if args.posonlyargs:
        parts.append("/")

    for a in args.args:
        parts.append(a.arg)

    if args.vararg:
        parts.append(f"*{args.vararg.arg}")

    # kw-only args
    for a in args.kwonlyargs:
        parts.append(a.arg)

    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    # apply defaults (positional + kw-only)
    defaults = list(args.defaults)
    if defaults:
        # defaults align to the last N positional args
        for i in range(1, len(defaults) + 1):
            arg_name = args.args[-i].arg
            parts_index = parts.index(arg_name)
            parts[parts_index] = f"{arg_name}={_format_default(defaults[-i])}"

    # kw-only defaults
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        if d is None:
            continue
        name = a.arg
        try:
            idx = parts.index(name)
            parts[idx] = f"{name}={_format_default(d)}"
        except ValueError:
            pass

    return f"{fn.name}({', '.join(parts)})"


CATEGORY_ORDER: list[tuple[str, list[str]]] = [
    (
        "Safety & governance",
        [
            "get_risk_disclosure",
            "accept_risk_disclosure",
            "get_advanced_risk_disclosure",
            "accept_advanced_risk_disclosure",
            "get_policy_overrides",
            "set_policy_overrides",
            "get_execution_preferences",
            "set_execution_preferences",
            "list_pending_executions",
            "confirm_execution",
            "cancel_execution",
            "validate_trade_risk",
        ],
    ),
    (
        "Execution (DEX/CEX)",
        [
            "swap_tokens",
            "transfer_eth",
            "place_cex_order",
            "get_cex_order",
            "cancel_cex_order",
            "wait_for_cex_order",
            "get_cex_balance",
            "get_cex_capabilities",
            "list_cex_open_orders",
            "list_cex_orders",
            "get_cex_my_trades",
            "cancel_all_cex_orders",
            "replace_cex_order",
        ],
    ),
    (
        "Paper trading",
        [
            "deposit_paper_funds",
            "place_limit_order",
            "check_orders",
            "get_address_balance",
        ],
    ),
    (
        "Market data",
        [
            "get_crypto_price",
            "get_ticker",
            "fetch_ohlcv",
            "get_market_regime",
            "get_marketdata_capabilities",
            "get_marketdata_status",
            "ingest_ticker",
            "ingest_ohlcv",
        ],
    ),
    (
        "Websockets (Phase 2.5)",
        [
            "start_marketdata_ws",
            "stop_marketdata_ws",
            "start_cex_private_ws",
            "stop_cex_private_ws",
            "list_cex_private_updates",
        ],
    ),
    (
        "Research & evaluation",
        [
            "run_backtest_simulation",
            "run_synthetic_stress_test",
            "analyze_performance",
        ],
    ),
    (
        "Intelligence feeds",
        [
            "get_sentiment",
            "get_news",
            "get_social_sentiment",
            "get_financial_news",
        ],
    ),
    (
        "Ops / observability",
        [
            "get_health",
            "get_metrics_snapshot",
        ],
    ),
    (
        "Misc",
        [
            "get_capabilities",
        ],
    ),
]


def main() -> int:
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    tools: dict[str, ast.FunctionDef] = {}

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and any(_is_mcp_tool_decorator(d) for d in node.decorator_list):
            tools[node.name] = node

    # Build sections in order; keep leftovers at the end.
    used: set[str] = set()
    lines: list[str] = []

    lines.append("## ReadyTrader-Crypto MCP Tool Catalog")
    lines.append("")
    lines.append("This file is generated from `server.py`.")
    lines.append("")
    lines.append("Regenerate with:")
    lines.append("")
    lines.append("```bash")
    lines.append("python tools/generate_tool_docs.py")
    lines.append("```")
    lines.append("")

    for section, names in CATEGORY_ORDER:
        present = [n for n in names if n in tools]
        if not present:
            continue
        used.update(present)
        lines.append(f"### {section}")
        lines.append("")
        for name in present:
            fn = tools[name]
            sig = _signature(fn)
            doc = (ast.get_docstring(fn) or "").strip()
            first = doc.splitlines()[0].strip() if doc else ""
            lines.append(f"- **`{sig}`**")
            if first:
                lines.append(f"  - {first}")
            lines.append("")

    leftovers = sorted(set(tools) - used)
    if leftovers:
        lines.append("### Uncategorized")
        lines.append("")
        for name in leftovers:
            fn = tools[name]
            sig = _signature(fn)
            doc = (ast.get_docstring(fn) or "").strip()
            first = doc.splitlines()[0].strip() if doc else ""
            lines.append(f"- **`{sig}`**")
            if first:
                lines.append(f"  - {first}")
            lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(tools)} tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

