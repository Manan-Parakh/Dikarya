"""Data retrieval helpers for the PyQt dashboard.

Reads logged experiment records from the CSV written by data_insert.py and
filters them by date range and experiment number.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

import pandas as pd

_LOG_PATH = Path("Logs") / "experiment_records.csv"

_COLUMNS = [
    "date",
    "time",
    "experiment",
    "temp_1",
    "temp_2",
    "weight_1",
    "weight_2",
    "difference",
    "room_temp",
]


def _extract_experiment_number(value: str) -> int | None:
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else None


def get_data_by_date_and_experiment(
    start_date: str,
    end_date: str,
    experiment_numbers: Sequence[int],
    csv_path: Path | str = _LOG_PATH,
) -> pd.DataFrame:
    """Return experiment rows within the requested date bounds and experiment ids."""
    path = Path(csv_path)
    if not path.exists():
        return pd.DataFrame(columns=_COLUMNS)

    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=_COLUMNS)

    for col in _COLUMNS:
        if col not in df.columns:
            df[col] = ""

    experiments_set = {int(num) for num in experiment_numbers}
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["exp_num"] = df["experiment"].apply(_extract_experiment_number)

    start = pd.to_datetime(start_date, errors="coerce").date()
    end = pd.to_datetime(end_date, errors="coerce").date()

    mask = (
        df["date_dt"].between(start, end, inclusive="both")
        & df["exp_num"].isin(experiments_set)
    )

    filtered = df.loc[mask, _COLUMNS].reset_index(drop=True)
    return filtered
