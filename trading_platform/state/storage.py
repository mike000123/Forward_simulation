from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class Paths:
    root: Path

    @property
    def signals_file(self) -> Path:
        return self.root / "signals.csv"

    @property
    def orders_file(self) -> Path:
        return self.root / "orders.csv"

    @property
    def events_file(self) -> Path:
        return self.root / "events.log"

    @property
    def run_config_dir(self) -> Path:
        return self.root / "configs"


def ensure_storage(root: str = "storage") -> Paths:
    p = Paths(root=Path(root))
    p.root.mkdir(parents=True, exist_ok=True)
    p.run_config_dir.mkdir(parents=True, exist_ok=True)
    return p


def append_records(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    frame = pd.DataFrame(records)
    if path.exists():
        existing = pd.read_csv(path)
        frame = pd.concat([existing, frame], ignore_index=True)
    frame.to_csv(path, index=False)


def log_event(paths: Paths, message: str, payload: dict[str, Any]) -> None:
    with paths.events_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"message": message, "payload": payload}, default=str) + "\n")


def save_config_snapshot(paths: Paths, name: str, config_obj: Any) -> Path:
    snapshot = paths.run_config_dir / f"{name}.json"
    with snapshot.open("w", encoding="utf-8") as f:
        if hasattr(config_obj, "__dataclass_fields__"):
            json.dump(asdict(config_obj), f, indent=2, default=str)
        else:
            json.dump(config_obj, f, indent=2, default=str)
    return snapshot
