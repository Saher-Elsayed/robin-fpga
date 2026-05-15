"""Benchmark catalogue loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional


@dataclass
class Benchmark:
    """One benchmark design entry."""

    name: str
    workload_class: str
    rtl_path: Path
    constraints_path: Path
    target_clock_ns: float
    expected_luts: int
    split: str            # "train" | "validation" | "held_out"
    license: str
    notes: str = ""


class BenchmarkCatalogue:
    """Loads and iterates over the 14-design benchmark suite.

    Reads from `data/benchmarks/manifest.json` by default.
    """

    def __init__(self, manifest_path: str | Path = "data/benchmarks/manifest.json") -> None:
        self.manifest_path = Path(manifest_path)
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"benchmark manifest not found at {self.manifest_path}")
        with open(self.manifest_path) as f:
            self.manifest = json.load(f)
        self._designs = {entry["name"]: entry for entry in self.manifest["designs"]}

    def __iter__(self) -> Iterator[Benchmark]:
        for entry in self._designs.values():
            yield self._make_benchmark(entry)

    def __len__(self) -> int:
        return len(self._designs)

    def __getitem__(self, name: str) -> Benchmark:
        if name not in self._designs:
            raise KeyError(f"benchmark '{name}' not in catalogue; available: {list(self._designs)}")
        return self._make_benchmark(self._designs[name])

    def by_class(self, workload_class: str) -> list[Benchmark]:
        return [self._make_benchmark(e) for e in self._designs.values()
                if e["workload_class"] == workload_class]

    def by_split(self, split: str) -> list[Benchmark]:
        return [self._make_benchmark(e) for e in self._designs.values()
                if e["split"] == split]

    def _make_benchmark(self, entry: dict) -> Benchmark:
        base = self.manifest_path.parent
        return Benchmark(
            name=entry["name"],
            workload_class=entry["workload_class"],
            rtl_path=base / entry["rtl_path"],
            constraints_path=base / entry["constraints_path"],
            target_clock_ns=float(entry["target_clock_ns"]),
            expected_luts=int(entry["expected_luts"]),
            split=entry["split"],
            license=entry["license"],
            notes=entry.get("notes", ""),
        )
