from __future__ import annotations

import argparse
import json

from src.finskillkg.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Financial KG + Skill KG 구축")
    parser.add_argument("--data", default="data/sample_financials.csv")
    parser.add_argument("--skills", default="skills")
    parser.add_argument("--output", default="outputs")
    args = parser.parse_args()

    summary = run_pipeline(args.data, args.skills, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
