from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.finskillkg.config import DartConfig
from src.finskillkg.dart import OpenDartClient
from src.finskillkg.normalize import normalize_dart_records


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenDART 재무제표 수집")
    parser.add_argument("--companies", nargs="+", required=True)
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--output", default="data/dart_financials.csv")
    args = parser.parse_args()

    config = DartConfig.from_env()
    client = OpenDartClient(config.api_key, timeout=config.timeout)
    codes = client.company_codes()

    frames = []
    for company_name in args.companies:
        if company_name not in codes:
            raise KeyError(f"OpenDART 기업코드를 찾지 못했습니다: {company_name}")
        corp_code = codes[company_name]

        for year in args.years:
            records = client.financial_statement_all(corp_code, year, fs_div="CFS")
            if not records:
                records = client.financial_statement_all(corp_code, year, fs_div="OFS")
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
            frames.append(frame)
            print(f"[ok] {company_name} {year}: {len(frame)} metrics")

    if not frames:
        raise RuntimeError("저장할 재무 데이터가 없습니다.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(frames, ignore_index=True).to_csv(output, index=False)
    print(f"saved: {output}")


if __name__ == "__main__":
    main()
