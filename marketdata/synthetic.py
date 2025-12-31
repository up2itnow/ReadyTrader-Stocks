from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import pandas as pd


@dataclass(frozen=True)
class SyntheticEvent:
    kind: str
    index: int
    magnitude: float
    description: str


def _utc_now_floor_hour() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(minute=0, second=0, microsecond=0)


def _gen_regime_plan(rng: random.Random, length: int) -> List[Tuple[str, int]]:
    """
    Returns a list of (regime_name, regime_length) segments that sum to length.
    """
    regimes = ["trend_up", "trend_down", "range", "volatile"]
    remaining = length
    plan: List[Tuple[str, int]] = []
    while remaining > 0:
        regime = rng.choice(regimes)
        seg = min(remaining, rng.randint(max(8, length // 20), max(12, length // 5)))
        plan.append((regime, seg))
        remaining -= seg
    # normalize exact sum
    if plan:
        total = sum(seg for _, seg in plan)
        if total != length:
            last_regime, last_seg = plan[-1]
            plan[-1] = (last_regime, last_seg + (length - total))
    return plan


def generate_synthetic_ohlcv(
    *,
    seed: int,
    length: int = 500,
    timeframe: str = "1h",
    start_price: float = 100.0,
    base_vol: float = 0.01,
    black_swan_prob: float = 0.02,
    parabolic_prob: float = 0.02,
) -> Dict[str, Any]:
    """
    Deterministic synthetic market generator.

    - Uses seeded RNG for deterministic replay
    - Stitches multiple regimes
    - Injects black swans and parabolic blow-off tops

    This generator is not intended to model real market microstructure.
    It exists to stress strategies across varied regimes and tail events while remaining reproducible by seed.

    Returns:
      { df: pd.DataFrame, meta: {...} }
    """
    if length < 50:
        raise ValueError("length must be >= 50")
    if start_price <= 0:
        raise ValueError("start_price must be > 0")
    if base_vol <= 0:
        raise ValueError("base_vol must be > 0")

    # Deterministic simulation RNG (not cryptographic).
    rng = random.Random(int(seed))  # nosec B311
    tf = timeframe.strip().lower()
    if tf.endswith("h"):
        step = timedelta(hours=int(tf[:-1] or "1"))
    elif tf.endswith("d"):
        step = timedelta(days=int(tf[:-1] or "1"))
    else:
        # default to hourly
        step = timedelta(hours=1)

    plan = _gen_regime_plan(rng, length)
    events: List[SyntheticEvent] = []
    regime_timeline: List[str] = []

    # Price process in log space
    log_p = math.log(start_price)

    # Event scheduling (deterministic)
    event_points: Dict[int, SyntheticEvent] = {}
    for i in range(length):
        roll = rng.random()
        if roll < black_swan_prob and i > 20 and i < length - 20:
            magnitude = rng.uniform(0.15, 0.55)  # crash size (15% to 55%)
            event_points[i] = SyntheticEvent(
                kind="black_swan_crash",
                index=i,
                magnitude=magnitude,
                description=f"Sudden crash of ~{magnitude:.0%} with volatility spike",
            )
        elif roll < black_swan_prob + parabolic_prob and i > 20 and i < length - 60:
            magnitude = rng.uniform(0.30, 1.20)  # run-up size proxy
            event_points[i] = SyntheticEvent(
                kind="parabolic_blowoff",
                index=i,
                magnitude=magnitude,
                description=f"Parabolic run-up then sharp reversal (strength={magnitude:.2f})",
            )

    def regime_params(name: str) -> Tuple[float, float]:
        # returns (drift_per_step, vol_per_step)
        if name == "trend_up":
            return (rng.uniform(0.0005, 0.0025), base_vol * rng.uniform(0.6, 1.2))
        if name == "trend_down":
            return (-rng.uniform(0.0005, 0.0025), base_vol * rng.uniform(0.6, 1.2))
        if name == "range":
            return (rng.uniform(-0.0002, 0.0002), base_vol * rng.uniform(0.4, 0.9))
        if name == "volatile":
            return (rng.uniform(-0.0003, 0.0003), base_vol * rng.uniform(1.5, 3.5))
        return (0.0, base_vol)

    # Build regime per index
    for name, seg_len in plan:
        regime_timeline.extend([name] * seg_len)
    regime_timeline = regime_timeline[:length]

    ts0 = _utc_now_floor_hour() - step * length
    rows: List[Dict[str, Any]] = []

    i = 0
    while i < length:
        regime = regime_timeline[i]
        drift, vol = regime_params(regime)

        # Event injection logic
        if i in event_points:
            ev = event_points[i]
            events.append(ev)
            if ev.kind == "black_swan_crash":
                # crash candle
                crash = -abs(ev.magnitude)
                log_p = log_p + crash
                # boost vol for a while
                vol = vol * 4.0
            elif ev.kind == "parabolic_blowoff":
                # create a parabolic ramp for N steps then reversal crash
                ramp_len = min(40, length - i - 10)
                strength = ev.magnitude
                for k in range(ramp_len):
                    # increasing drift (parabolic)
                    local_drift = drift + (k / max(1, ramp_len)) ** 2 * (0.01 * strength)
                    r = rng.gauss(local_drift, vol * 0.8)
                    prev = math.exp(log_p)
                    log_p = log_p + r
                    close = math.exp(log_p)
                    high = max(prev, close) * (1.0 + abs(rng.gauss(0, vol * 0.5)))
                    low = min(prev, close) * (1.0 - abs(rng.gauss(0, vol * 0.5)))
                    rows.append(
                        {
                            "timestamp": ts0 + step * (i + k),
                            "open": prev,
                            "high": high,
                            "low": low,
                            "close": close,
                            "volume": abs(rng.gauss(1_000, 200)),
                            "regime": regime_timeline[i + k],
                        }
                    )
                i = i + ramp_len
                # blow-off crash after ramp
                if i < length:
                    crash_mag = min(0.60, 0.20 + 0.30 * min(1.0, strength))
                    log_p = log_p - crash_mag
                continue

        # Normal candle evolution
        r = rng.gauss(drift, vol)
        prev = math.exp(log_p)
        log_p = log_p + r
        close = math.exp(log_p)

        # wickiness increases in volatile regimes
        wick = vol * (1.5 if regime == "volatile" else 1.0)
        high = max(prev, close) * (1.0 + abs(rng.gauss(0, wick * 0.6)))
        low = min(prev, close) * (1.0 - abs(rng.gauss(0, wick * 0.6)))

        # occasional gap moves
        if rng.random() < 0.01:
            gap = rng.uniform(-0.08, 0.08)
            prev = prev * (1.0 + gap)

        rows.append(
            {
                "timestamp": ts0 + step * i,
                "open": prev,
                "high": high,
                "low": low,
                "close": close,
                "volume": abs(rng.gauss(1_000, 200)),
                "regime": regime,
            }
        )
        i += 1

    df = pd.DataFrame(rows).iloc[:length].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df.reset_index(drop=True, inplace=True)

    meta = {
        "seed": int(seed),
        "length": int(length),
        "timeframe": timeframe,
        "start_price": float(start_price),
        "base_vol": float(base_vol),
        "events": [ev.__dict__ for ev in events],
        "regime_plan": plan,
    }
    return {"df": df, "meta": meta}

