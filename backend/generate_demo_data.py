#!/usr/bin/env python3
"""Generate the synthetic demo dataset used by MonsoonAI.

Usage (from the backend/ folder):

    python generate_demo_data.py                 # 540 days, default seed
    python generate_demo_data.py --days 900
    python generate_demo_data.py --out ../data/demo_rainfall.csv

Writes a district x day table with synthetic meteorological features, a
synthetic "observed" rainfall amount and a synthetic raw NWP forecast produced
by a regime-dependent error model. The data is clearly labelled
data_source=SYNTHETIC_DEMO and is not real weather data.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import DEMO_RAINFALL_CSV, RANDOM_SEED
from app.ml.synthetic import generate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic monsoon demo data.")
    parser.add_argument("--days", type=int, default=540)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--out", type=str, default=str(DEMO_RAINFALL_CSV))
    args = parser.parse_args()

    df = generate_dataset(n_days=args.days, seed=args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    print(f"Wrote {len(df):,} synthetic rows to {out}")
    print(f"Districts: {df['district'].nunique()}   Days: {df['date'].nunique()}")
    print("\nRegime distribution:")
    print(df["regime"].value_counts().to_string())
    print("\nRainfall summary (mm):")
    print(df[["raw_nwp_mm", "observed_rainfall_mm"]].describe().round(2).to_string())
    print("\nAll values are SYNTHETIC demo data, not real weather observations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
