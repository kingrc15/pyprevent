#!/usr/bin/env python3
"""
Compare pyprevent outputs to the live AHA PreventCalculate API (official web UI).

Example:
  python scripts/compare_aha_web.py
  python scripts/compare_aha_web.py --case table_s25_female_base
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.aha_web import (  # noqa: E402
    assert_case_matches_web,
    benchmark_cases,
    score_case_python,
    score_case_web,
    _model_suffix,
    _web_ten_year_map,
    _web_thirty_year_map,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        action="append",
        help="Run only case_id(s) from the benchmark set (repeatable).",
    )
    args = parser.parse_args()

    cases = benchmark_cases()
    if args.case:
        wanted = set(args.case)
        cases = [c for c in cases if c.case_id in wanted]
        missing = wanted - {c.case_id for c in cases}
        if missing:
            print("Unknown case_id(s):", ", ".join(sorted(missing)), file=sys.stderr)
            return 1

    failed = 0
    for case in cases:
        try:
            web_body = score_case_web(case)
            suffix = _model_suffix(web_body["modelName"])
            py_ten, py_thirty = score_case_python(case, model_suffix=suffix)
            web_ten = _web_ten_year_map(web_body)
            web_thirty = _web_thirty_year_map(web_body)
            assert_case_matches_web(case)
            print(f"OK  {case.case_id}  [{web_body['modelName']}]")
            print(f"    10yr  web={web_ten}  py={py_ten}")
            if web_thirty:
                print(f"    30yr  web={web_thirty}  py={py_thirty}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {case.case_id}: {exc}", file=sys.stderr)

    if failed:
        print(f"\n{failed} case(s) failed.", file=sys.stderr)
        return 1
    print(f"\nAll {len(cases)} case(s) match the AHA web API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
