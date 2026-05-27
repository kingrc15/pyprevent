from __future__ import annotations

"""
Lightweight coefficient audit between upstream R and this Python port.

This is intentionally mechanical: it checks that a curated set of sentinel
constants (intercepts and a few key slopes) appear verbatim in both sources.

It is not a mathematical proof of equality, but it does catch the most common
porting mistakes (wrong model block pasted, sign flips, or missing-coefficient
constants accidentally changed).
"""

import os
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_R_SOURCE = ROOT.parent / "PREVENT" / "R" / "AHAprevent" / "R" / "AHA_prevent_equations.R"
R_SOURCE = pathlib.Path(os.environ.get("PREVENT_R_SOURCE", DEFAULT_R_SOURCE))


SENTINELS = [
    # base
    "-3.307728",  # female 10yr CVD intercept
    "-3.031168",  # male 10yr CVD intercept
    "-1.318827",  # female 30yr CVD intercept
    "-1.148204",  # male 30yr CVD intercept
    # full
    "-3.860385",  # female 10yr full CVD intercept
    "-3.631387",  # male 10yr full CVD intercept
    # uacr
    "-3.738341",  # female 10yr uacr CVD intercept
    "-3.510705",  # male 10yr uacr CVD intercept
    # hba1c
    "-3.306162",  # female 10yr hba1c CVD intercept
    "-3.040901",  # male 10yr hba1c CVD intercept
    # sdi
    "-3.461564",  # female 10yr sdi CVD intercept
    "-3.159572",  # male 10yr sdi CVD intercept
]


def _read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    if not R_SOURCE.exists():
        print(
            f"SKIP: R source not found at {R_SOURCE} "
            "(set PREVENT_R_SOURCE to override)",
            file=sys.stderr,
        )
        return 0

    r_text = _read_text(R_SOURCE)
    py_text = ""
    for p in sorted((ROOT / "prevent").glob("**/*.py")):
        py_text += _read_text(p) + "\n"

    missing_in_r = [s for s in SENTINELS if s not in r_text]
    missing_in_py = [s for s in SENTINELS if s not in py_text]

    if missing_in_r or missing_in_py:
        if missing_in_r:
            print("Missing sentinels in R source:", file=sys.stderr)
            for s in missing_in_r:
                print(f"  - {s}", file=sys.stderr)
        if missing_in_py:
            print("Missing sentinels in Python source:", file=sys.stderr)
            for s in missing_in_py:
                print(f"  - {s}", file=sys.stderr)
        return 1

    bad_tokens = re.findall(r"\b\d+\.\d+\.\d+\b", py_text)
    if bad_tokens:
        print("ERROR: malformed numeric tokens detected in Python:", file=sys.stderr)
        for t in sorted(set(bad_tokens))[:20]:
            print(f"  - {t}", file=sys.stderr)
        return 1

    print("OK: coefficient sentinel audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
