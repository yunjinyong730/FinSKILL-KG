from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.finskillkg.cohort import load_dart_cohort
from src.finskillkg.config import DartConfig
from src.finskillkg.dart import OpenDartClient
from src.finskillkg.normalize import normalize_dart_records


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenDART 재무제표 수집")
    parser.add_argument("--config", default="config/dart_companies.yaml")
    parser.add_argument("--companies", nargs="+")
    parser.add_argument("--years", nargs="+", type=int)
    parser.add_argument("--output", default="data/dart_financials.csv")
    args = parser.parse_args()

    cohort = load_dart_cohort(args.config)
    companies = args.companies or [company.name for company in cohort.companies]
    years = args.years or list(cohort.years)

    config = DartConfig.from_env()
    client = OpenDartClient(config.api_key, timeout=config.timeout)
    codes = client.company_codes()

    frames = []
    collected = []
    for company_name in companies:
        if company_name not in codes:
            raise KeyError(f"OpenDART 기업코드를 찾지 못했습니다: {company_name}")
        corp_code = codes[company_name]

        for year in years:
            fs_div = "CFS"
            records = client.financial_statement_all(corp_code, year, fs_div=fs_div)
            if not records:
                fs_div = "OFS"
                records = client.financial_statement_all(corp_code, year, fs_div=fs_div)
            if not records:
                print(f"[skip] {company_name} {year}: 재무제표 없음")
                continue

            frame = normalize_dart_records(
                records,
                company_code=corp_code,
                company_name=company_name,
                year=year,
                default_source_id=f"{corp_code}-{year}-11011",
            )
            if frame.empty:
                print(f"[skip] {company_name} {year}: 지원 metric 없음")
                continue

            frame["fs_div"] = fs_div
            frames.append(frame)
            collected.append(
                {
                    "company_name": company_name,
                    "corp_code": corp_code,
                    "year": year,
                    "fs_div": fs_div,
                    "metrics": sorted(frame["metric"].tolist()),
                    "source_ids": sorted(frame["source_id"].unique().tolist()),
                }
            )
            print(f"[ok] {company_name} {year}: {len(frame)} metrics ({fs_div})")

    if not frames:
        raise RuntimeError("저장할 재무 데이터가 없습니다.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result = pd.concat(frames, ignore_index=True)
    result.to_csv(output, index=False)

    manifest = {
        "source": "OpenDART",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": str(args.config),
        "requested_companies": companies,
        "requested_years": years,
        "rows": int(len(result)),
        "collected": collected,
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"saved: {output}")
    print(f"saved: {manifest_path}")


if __name__ == "__main__":
    main()
