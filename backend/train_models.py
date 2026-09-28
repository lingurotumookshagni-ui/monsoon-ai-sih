#!/usr/bin/env python3
"""MonsoonAI model training entrypoint.

Usage (from the backend/ folder):

    python train_models.py                 # train everything with defaults
    python train_models.py --days 720      # longer synthetic record
    python train_models.py --rebuild-data  # regenerate data/demo_rainfall.csv

Trains the weather-regime classifier, the regime-specific rainfall correction
models and the heavy-rainfall probability models, evaluates them on a temporal
hold-out period and writes artefacts to models/ and outputs/.
"""
from __future__ import annotations

import argparse
import sys

from app.config import RANDOM_SEED
from app.ml.train import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Train MonsoonAI models (demo mode).")
    parser.add_argument("--days", type=int, default=540,
                        help="Number of synthetic days to generate (default: 540)")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED,
                        help="Random seed for reproducibility")
    parser.add_argument("--rebuild-data", action="store_true",
                        help="Regenerate data/demo_rainfall.csv even if it exists")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    args = parser.parse_args()

    run_pipeline(n_days=args.days, seed=args.seed,
                 rebuild_data=args.rebuild_data, verbose=not args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
