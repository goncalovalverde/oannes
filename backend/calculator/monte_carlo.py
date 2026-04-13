import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Optional

_now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: E731


def simulate_when_done(
    throughput_series: list,
    backlog_size: int,
    simulations: int = 10_000,
    start_date: Optional[str] = None,
    seed: Optional[int] = None,
) -> dict:
    """Monte Carlo: given backlog_size items remaining, when will they be done?

    Args:
        seed: RNG seed for reproducibility. Pass ``None`` (default) in production
              for genuinely random results. Pass a fixed value in tests.
    """
    if not throughput_series or backlog_size <= 0:
        return {
            "percentiles": {"50": None, "70": None, "85": None, "95": None},
            "histogram": [],
            "recommended_date": None
        }

    series = np.array([max(0, t) for t in throughput_series])
    if series.sum() == 0:
        return {
            "percentiles": {"50": None, "70": None, "85": None, "95": None},
            "histogram": [],
            "recommended_date": None
        }

    start = pd.Timestamp(start_date) if start_date else pd.Timestamp(_now())
    rng = np.random.default_rng(seed)

    weeks_needed = []
    for _ in range(simulations):
        total = 0
        w = 0
        while total < backlog_size and w < 520:
            total += rng.choice(series)
            w += 1
        if w >= 520:
            import logging
            logging.getLogger(__name__).warning(
                "simulate_when_done: simulation hit 520-week cap for backlog_size=%d — "
                "throughput may be too low relative to backlog.",
                backlog_size,
            )
        weeks_needed.append(w)

    weeks_array = np.array(weeks_needed)

    p50 = int(np.percentile(weeks_array, 50))
    p70 = int(np.percentile(weeks_array, 70))
    p85 = int(np.percentile(weeks_array, 85))
    p95 = int(np.percentile(weeks_array, 95))

    def weeks_to_date(w: int) -> str:
        return (start + pd.Timedelta(weeks=w)).strftime("%Y-%m-%d")

    max_w = int(np.percentile(weeks_array, 99))
    bins = range(1, max_w + 2)
    hist, edges = np.histogram(weeks_array, bins=bins, density=False)
    cumulative = np.cumsum(hist) / simulations

    histogram = [
        {"weeks": int(edges[i]), "probability": float(h / simulations), "cumulative": float(c)}
        for i, (h, c) in enumerate(zip(hist, cumulative))
    ]

    return {
        "percentiles": {
            "50": weeks_to_date(p50),
            "70": weeks_to_date(p70),
            "85": weeks_to_date(p85),
            "95": weeks_to_date(p95),
        },
        "histogram": histogram,
        "recommended_date": weeks_to_date(p85),
    }


def simulate_how_many(
    throughput_series: list,
    weeks: int,
    simulations: int = 10_000,
    seed: Optional[int] = None,
) -> dict:
    """Monte Carlo: in N weeks, how many items will be done?

    Args:
        seed: RNG seed for reproducibility. Pass ``None`` (default) in production.
    """
    if not throughput_series or weeks <= 0:
        return {
            "percentiles": {"50": None, "70": None, "85": None, "95": None},
            "histogram": []
        }

    series = np.array([max(0, t) for t in throughput_series])
    rng = np.random.default_rng(seed)

    totals = rng.choice(series, size=(simulations, weeks), replace=True).sum(axis=1).astype(int)

    p50 = int(np.percentile(totals, 50))
    p70 = int(np.percentile(totals, 70))
    p85 = int(np.percentile(totals, 85))
    p95 = int(np.percentile(totals, 95))

    min_v, max_v = int(totals.min()), int(totals.max())
    bins = range(min_v, max_v + 2)
    hist, edges = np.histogram(totals, bins=bins, density=False)
    cumulative = np.cumsum(hist) / simulations  # O(n) — fixed from O(n²) loop

    histogram = [
        {"items": int(edges[i]), "probability": float(h / simulations), "cumulative": float(c)}
        for i, (h, c) in enumerate(zip(hist, cumulative))
    ]

    return {
        "percentiles": {"50": p50, "70": p70, "85": p85, "95": p95},
        "histogram": histogram,
    }
