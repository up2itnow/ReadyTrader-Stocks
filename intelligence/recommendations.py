from __future__ import annotations

from typing import Any, Dict, List, Tuple


def recommend_settings(stress_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce conservative, heuristic recommendations based on stress outcomes.
    If the strategy defines PARAMS keys, we will recommend updates for matching keys.
    """
    metrics = (stress_summary or {}).get("metrics", {}) or {}
    detected = (stress_summary or {}).get("strategy_params_detected", {}) or {}

    mdd_max = float(metrics.get("max_drawdown_max", 0.0) or 0.0)
    mdd_p95 = float(metrics.get("max_drawdown_p95", 0.0) or 0.0)
    ret_p05 = float(metrics.get("return_p05", 0.0) or 0.0)
    trades_mean = float(metrics.get("trades_mean", 0.0) or 0.0)

    recs: List[Dict[str, Any]] = []
    param_updates: Dict[str, Any] = {}

    def suggest_param(key: str, value: Any, reason: str, safe_range: Tuple[Any, Any] | None = None):
        if key in detected:
            param_updates[key] = value
        recs.append(
            {
                "category": "parameter_update" if key in detected else "guidance",
                "param": key,
                "recommended": value,
                "safe_range": list(safe_range) if safe_range else None,
                "reason": reason,
                "applies": key in detected,
            }
        )

    # Tail risk / drawdown controls
    if mdd_max >= 0.35 or mdd_p95 >= 0.25:
        suggest_param(
            "max_alloc_pct",
            0.02,
            "High tail drawdowns detected in synthetic stress. Reduce max position sizing per trade.",
            (0.005, 0.05),
        )
        suggest_param(
            "cooldown_bars",
            10,
            (
                "Stress scenarios suggest rapid compounding losses; add a cooldown after exits or losses "
                "to reduce churn in volatility clusters."
            ),
            (0, 50),
        )

    # Negative tail returns: reduce risk / require stronger signals
    if ret_p05 <= -0.10:
        suggest_param(
            "min_signal_strength",
            0.2,
            (
                "5th percentile returns are strongly negative; require stronger signals before entering "
                "to avoid overtrading in chop."
            ),
            (0.0, 1.0),
        )
        suggest_param(
            "regime_filter_adx_min",
            20,
            "Add/raise a trend-strength filter to avoid mean-reversion losses during high-volatility trends.",
            (10, 40),
        )

    # Overtrading
    if trades_mean >= 80:
        suggest_param(
            "debounce_bars",
            3,
            "High trade frequency under stress; add debounce (minimum bars between trades) to reduce whipsaw.",
            (0, 20),
        )

    return {
        "recommended_params": param_updates,
        "recommendations": recs,
        "notes": [
            "Recommendations are heuristic and should be validated via backtests and (later) walk-forward analysis.",
            (
                "If your strategy exposes PARAMS keys, matching keys are returned in recommended_params "
                "for easy application."
            ),
        ],
    }

