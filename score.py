"""Score firstwrong.py against tests/cases/.

Each case file is named <topic>-<expect>.txt where <expect> is "l<n>" for the
line that should be reported, or "ok" for working with no wrong line.

    py -3 score.py
    py -3 score.py --only trig

False positives on correct working are counted and printed separately, not
folded into an accuracy number. A checker that invents errors in correct work
is worse than no checker, so that class has to stay visible.
"""

import argparse
import glob
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
COST_PER_CASE = 0.002  # one model call, roughly

LINE = re.compile(r"Line (\d+) is where it goes wrong")
NONE = re.compile(r"No wrong line found")
BLOCK = re.compile(r"BLOCKED")


def expected(path):
    """"l3" -> 3, "ok" -> None, from the filename suffix."""
    tail = os.path.basename(path)[:-4].rsplit("-", 1)[-1]
    return None if tail == "ok" else int(tail.lstrip("l"))


def run(path):
    out = subprocess.run([sys.executable, os.path.join(HERE, "firstwrong.py"), path],
                         capture_output=True, encoding="utf-8", errors="replace",
                         timeout=400)
    text = (out.stdout or "") + (out.stderr or "")
    m = LINE.search(text)
    if m:
        return int(m.group(1))
    if NONE.search(text):
        return None
    if BLOCK.search(text):
        return "blocked"
    return "unparsed: " + " ".join(text.split())[:80]


def verdict(want, got):
    if isinstance(got, str):
        return "blocked" if got == "blocked" else "unparsed"
    if want is None:
        return "exact" if got is None else "FALSE POSITIVE"
    if got is None:
        return "false negative"
    return "exact" if got == want else "wrong line"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="substring filter on filename")
    args = ap.parse_args()

    files = sorted(f for f in glob.glob(os.path.join(HERE, "tests", "cases", "*.txt"))
                   if args.only in os.path.basename(f))
    if not files:
        print("no cases matched")
        return 1

    print("running %d cases (~$%.2f)..." % (len(files), len(files) * COST_PER_CASE))
    # Four at a time: each case is a ~10s model call and they are independent.
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, files))

    tally = {}
    print()
    print("  %-34s %-8s %-10s %s" % ("case", "expect", "got", "verdict"))
    print("  " + "-" * 74)
    for path, got in zip(files, results):
        want = expected(path)
        v = verdict(want, got)
        tally[v] = tally.get(v, 0) + 1
        show = "none" if got is None else str(got)
        print("  %-34s %-8s %-10s %s" % (os.path.basename(path)[:-4],
                                         "none" if want is None else "l%d" % want,
                                         show[:10], v))

    correct_cases = sum(1 for f in files if expected(f) is None)
    fp = tally.get("FALSE POSITIVE", 0)
    print()
    print("  exact matches        : %d / %d" % (tally.get("exact", 0), len(files)))
    print("  wrong line reported  : %d" % tally.get("wrong line", 0))
    print("  false negatives      : %d" % tally.get("false negative", 0))
    print("  blocked              : %d" % tally.get("blocked", 0))
    if tally.get("unparsed"):
        print("  unparsed output      : %d" % tally["unparsed"])
    print()
    print("  FALSE POSITIVES ON CORRECT WORKING : %d / %d correct cases"
          % (fp, correct_cases))
    if fp:
        print("  ^ this is the class that makes the tool untrustworthy.")
        for path, got in zip(files, results):
            if verdict(expected(path), got) == "FALSE POSITIVE":
                print("      %s -> invented an error at line %s"
                      % (os.path.basename(path)[:-4], got))
    print()
    print("  run cost: about $%.2f" % (len(files) * COST_PER_CASE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
