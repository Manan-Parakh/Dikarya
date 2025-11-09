"""Utility helpers for persisting experiment records produced by the GUI.

The GUI writes each record from a background thread, so this module keeps the
file operations lightweight and thread-safe. Data is appended to
Logs/experiment_records.csv for easy auditing/debugging.
"""

from __future__ import annotations

import csv
import threading
from pathlib import Path
from typing import Mapping

from helper.paths import get_project_root

PROJECT_ROOT = get_project_root()
_LOG_DIR = PROJECT_ROOT / "Logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_CSV_PATH = _LOG_DIR / "experiment_records.csv"

_HEADERS = (
    "date",
    "time",
    "experiment",
    "temp_1",
    "temp_2",
    "weight_1",
    "weight_2",
    "difference",
    "room_temp",
)

# This is a lock to ensure that only one thread writes to the experiment_records.csv file at a time, making file operations thread-safe.
_FILE_LOCK = threading.Lock()


def insert_experiment_record(
    record: Mapping[str, str], *, csv_path: Path | str = _CSV_PATH
) -> None:
    """Append a single experiment record to the CSV log."""
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {field: str(record.get(field, "")) for field in _HEADERS}

    try:
        with _FILE_LOCK:
            file_exists = path.exists()
            with path.open("a", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=_HEADERS)
                if not file_exists or path.stat().st_size == 0:
                    writer.writeheader()
                writer.writerow(row)
    except Exception as exc:
        print(f"[data_insert] Failed to persist experiment record: {exc}")
