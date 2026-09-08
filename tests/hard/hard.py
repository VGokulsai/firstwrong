# -*- coding: utf-8 -*-
"""Cases built to break firstwrong.py, plus the runner that scores them.

score.py only globs tests/cases/, and its expected() would crash on a
"blocked" suffix, so this file carries its own copy of the parse and verdict
logic rather than editing anything outside tests/hard/.

    py -3 tests/hard/hard.py --write     write the .txt cases (idempotent)
    py -3 tests/hard/hard.py             write, then run them all
    py -3 tests/hard/hard.py --only amb   filter by filename substring

Every case's expectation, and the reasoning behind it, is the comment above
it. Those comments were written before anything was run and are not edited
afterwards; where the tool disagreed, the disagreement is the result.
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
ROOT = os.path.dirname(os.path.dirname(HERE))
COST_PER_CASE = 0.002

CASES = {

# 1. TWO ERRORS. First on line 2 (x = 3 - y, should be x = 3 + y).
#    Second on line 6: given line 5 (9 - y = 16) it is y = -7, not y = 7 - a
#    genuinely separate slip, not a knock-on. Naming line 6 finds a real error
#    and is still a failure.
"twoerrors-sim-l2.txt": """Solve the simultaneous equations 3x + 2y = 16 and x - y = 3

3x + 2y = 16 ... (i) and x - y = 3 ... (ii)
From (ii), x = 3 - y
Substituting in (i): 3(3 - y) + 2y = 16
9 - 3y + 2y = 16
9 - y = 16
y = 7
x = 3 - 7 = -4
""",

# 2. TWO ERRORS, subtle first and blatant second. First: line 3, since
#    40 + 12 + 48 = 100, not 90. Second: line 5, 0.25 x 90 = 22.5, not 2250 -
#    an order-of-magnitude howler that a checker may be pulled towards.
"twoerrors-caco3-l3.txt": """Calculate the mass of 0.25 mol of CaCO3. Ca = 40, C = 12, O = 16

Molar mass of CaCO3 = Ca + C + 3 x O
= 40 + 12 + 48
= 90 g/mol
Mass = moles x molar mass = 0.25 x 90
= 2250 g
""",

# 3. ARITHMETICALLY CORRECT, LOGICALLY UNJUSTIFIED. C really is 70, so every
#    number on line 3 checks out. But nothing given says the triangle is
#    isosceles, and with A = 50 and B = 60 it is not. The stated reason is
#    false and does not follow from the lines before it. Expect line 3.
"unjustified-triangle-l3.txt": """In triangle ABC, angle A = 50 degrees and angle B = 60 degrees. Find angle C

A + B + C = 180
50 + 60 + C = 180
Since the triangle is isosceles, C = 70
C = 70 degrees
""",

# 4. LOGICALLY UNJUSTIFIED CONCLUSION. Line 2 is right and the ratio really is
#    2 : 1 as required, so the arithmetic on line 3 is fine. The conclusion
#    drawn from it is not: exact stoichiometry means neither reagent limits.
#    Line 4 then happens to be true. Expect line 3.
"unjustified-limiting-l3.txt": """4 g of H2 reacts with 32 g of O2 to form water. Which is the limiting reagent? H = 1, O = 16

2H2 + O2 -> 2H2O
Moles of H2 = 4/2 = 2 and moles of O2 = 32/32 = 1
The ratio required is 2 : 1 and we have 2 : 1, so O2 is the limiting reagent
The mass of water formed is 2 x 18 = 36 g
""",

# 5. ERROR INSIDE A CORRECT FINAL ANSWER. Line 3 is wrong (45/5 = 9, not 8).
#    Line 4 quietly repairs it and lands on the right answer, 3 s. A checker
#    that reads backwards from the answer sees nothing. Expect line 3.
"cancels-freefall-l3.txt": """A stone is dropped from rest from a height of 45 m. Find the time it takes to reach the ground. Take g = 10 m/s^2

u = 0, so h = (1/2)gt^2 gives 45 = (1/2)(10)t^2
45 = 5t^2
t^2 = 45/5 = 8
t = 3 s
""",

# 6. ERROR INSIDE A CORRECT FINAL ANSWER, harder than case 5. Line 3 says
#    19 x 4 = 74 (it is 76). Line 4 silently uses 76 and the final 820 is
#    correct, so unlike case 5 the last line is arithmetically consistent with
#    the true value and reads perfectly. Expect line 3.
"cancels-ap-l3.txt": """Find the sum of the first 20 terms of the AP 3, 7, 11, ...

a = 3, d = 4, n = 20
S20 = (n/2)[2a + (n - 1)d] = 10[6 + 19 x 4]
19 x 4 = 74
S20 = 10[6 + 76] = 10 x 82 = 820
""",

# 7. AMBIGUOUS NOTATION, correct under the standard reading. 2x/3y read as
#    (2x)/(3y) gives 2; the other reading, (2x/3)y, gives 8. The working
#    declares which reading it takes and stays consistent, so nothing is
#    wrong. Expect no wrong line. A tool that invents an error over notation
#    it could have read either way fails this.
"ambig-2x3y-ok.txt": """If x = 6 and y = 2, find the value of 2x/3y

2x/3y = (2x)/(3y)
= (2 x 6)/(3 x 2)
= 12/6
= 2
""",

# 8. MISSING BRACKET THAT CHANGES THE MEANING. 6 / 2 x 3 under the usual
#    left-to-right rule for equal-precedence operators is 9; the working reads
#    it as 6/(2 x 3) = 1. Expect line 2, held loosely: this is the one case
#    where BLOCKED would be the better answer, since the expression really is
#    badly posed. "ok" I would not accept - that silently endorses one reading
#    of an ambiguity and tells the student their answer is safe.
"ambig-bracket-l2.txt": """Evaluate 6 / 2 x 3

6 / 2 x 3
= 6 / 6
= 1
""",

# 9. IMPLIED MULTIPLICATION UNDER AN EXPONENT. ab^2 means a(b^2) = 3 x 16 =
#    48; the working reads it as (ab)^2. Unlike case 8 this is not genuinely
#    ambiguous - the exponent binds to b alone - but it reads like an
#    ambiguity. Expect line 2.
"ambig-abexp-l2.txt": """If a = 3 and b = 4, evaluate ab^2

ab^2 with a = 3 and b = 4
ab^2 = (ab)^2
= (3 x 4)^2
= 144
""",

# 10. sin^-1 AS ARCSIN, NOT 1/sin. Getting 30 out rather than the 150 that
#     went in looks like a mistake, and the range restriction on line 2 is the
#     whole point. Every line is correct. Expect no wrong line. Doubles as a
#     correct-working-that-looks-wrong case.
"ambig-arcsin-ok.txt": """Evaluate sin^-1(sin 150 degrees), giving the answer in degrees

sin 150 = sin(180 - 150) = sin 30 = 1/2
The principal value of sin^-1 lies between -90 and 90 degrees
sin^-1(1/2) = 30 degrees
So sin^-1(sin 150 degrees) = 30 degrees
""",

# 11. ANSWERS A DIFFERENT QUESTION. The question asks for the time of flight;
#     the working correctly finds the maximum height instead. Every line
#     follows from the one before and no line is false.
#     HONEST EXPECTATION: no wrong line. The README is explicit that the tool
#     checks each line against the last and does NOT check that you answered
#     the question asked - "Correct steps to the wrong question is still
#     wrong, and this tool cannot tell you that" - and the no-wrong-line
#     message itself carries that caveat. Any reported line number here is a
#     false positive: it would send the student to a line that is not wrong,
#     and they would never find anything there. The failure in this working is
#     real but it is out of scope by design, and the honest place to fix that
#     is the README's Limits section, not a line number.
"differentquestion-ok.txt": """A projectile is fired at 40 m/s at 30 degrees to the horizontal. Find its time of flight. Take g = 10 m/s^2

u = 40 m/s at 30 degrees, so the vertical component is u_y = 40 sin 30 = 20 m/s
At the highest point the vertical velocity is zero
Using v^2 = u_y^2 - 2gH with v = 0: 0 = 400 - 2(10)H
20H = 400
H = 20 m
""",

# 12. BLOCKED: under-specified. No height is given, so the area cannot be
#     found. Every line of working is true and follows from the last, which is
#     the trap - a line-by-line checker sees a clean sheet. solvable must come
#     back false, because "no wrong line" on an unanswerable question reads as
#     a pass.
"underspec-triangle-blocked.txt": """A triangle has a base of 10 cm. Find its area

Area = (1/2) x base x height
Area = (1/2) x 10 x h
Area = 5h cm^2
""",

# 13. BLOCKED: the information needed is missing. Charles' law is applied
#     correctly, but no temperature is given anywhere, so V2 cannot be found.
#     Again every line is internally fine.
"missinginfo-gas-blocked.txt": """A gas occupies 2 litres. Find the volume it occupies after it is heated at constant pressure

At constant pressure V1/T1 = V2/T2
2/T1 = V2/T2
V2 = 2 x T2/T1
""",

# 14. BLOCKED: impossible premise. 3, 4 and 6 cannot be the sides of a
#     right-angled triangle, since 9 + 16 = 25 while 6^2 = 36. The working
#     demonstrates exactly that and stops. There is no wrong line and there is
#     no answer, so BLOCKED is the honest output and a clean sheet is not.
"contradictory-triangle-blocked.txt": """A right-angled triangle has sides 3 cm, 4 cm and 6 cm. Find the length of its hypotenuse

The hypotenuse would be the longest side, which is 6 cm
By Pythagoras the other two sides must satisfy 3^2 + 4^2 = 6^2
3^2 + 4^2 = 9 + 16 = 25
6^2 = 36
25 is not equal to 36
""",

# 15. VERY SHORT WORKING, wrong. Two lines and no intermediate step to lean
#     on: 91/7 = 13, not 12. Expect line 2.
"short-l2.txt": """Find x if 7x = 91

7x = 91
x = 12
""",

# 16. VERY SHORT WORKING, correct. a10 = 5 + 9d = 41. Two lines, the second
#     compressing formula, substitution and arithmetic into one - very little
#     shown, which is where a nervous checker invents an error. Expect no
#     wrong line.
"short-ok.txt": """Find the 10th term of the AP 5, 9, 13, ...

a = 5 and d = 4
a10 = a + 9d = 5 + 9 x 4 = 41
""",

# 17. CORRECT BUT READS WRONG: Cartesian sign convention. u, f and v all come
#     out negative and v = -60 cm looks like a dropped sign, but it is right:
#     1/v = 1/f - 1/u = -1/20 + 1/30 = -1/60. Expect no wrong line.
"signconvention-mirror-ok.txt": """An object is placed 30 cm in front of a concave mirror of focal length 20 cm. Find the image distance using the Cartesian sign convention

Using the convention, u = -30 cm and f = -20 cm
From 1/v + 1/u = 1/f, 1/v = 1/f - 1/u = -1/20 - (-1/30)
1/v = -1/20 + 1/30 = (-3 + 2)/60 = -1/60
v = -60 cm
The image is 60 cm in front of the mirror, so it is real
""",

# 18. CORRECT BUT READS WRONG: proving an identity by cross-multiplying the
#     statement being proved. That usually signals circular reasoning, but
#     line 1 establishes both denominators are non-zero on the stated domain,
#     so each step is reversible and the chain is a valid equivalence.
#     Expect no wrong line.
"unusualidentity-ok.txt": """Prove that sin(theta)/(1 + cos theta) = (1 - cos theta)/sin(theta) for 0 < theta < 180 degrees

For 0 < theta < 180, sin theta is not 0 and 1 + cos theta is not 0, so both denominators are non-zero
The statement is therefore equivalent to sin^2(theta) = (1 + cos theta)(1 - cos theta)
(1 + cos theta)(1 - cos theta) = 1 - cos^2(theta)
1 - cos^2(theta) = sin^2(theta)
Both sides are equal, so the identity holds
""",

# 19. SUBTLE PHYSICS ARITHMETIC. Line 3 drops the cos 60 factor it has just
#     quoted correctly: 2 x 3 x 4 x (1/2) = 12, so R^2 = 37, not 49. Quoting
#     cos 60 = 1/2 right there makes the slip easy to read past, and the tidy
#     R = 7 on line 4 sells it. Expect line 3.
"vectorresultant-l3.txt": """Two forces of 3 N and 4 N act at a point with an angle of 60 degrees between them. Find the magnitude of the resultant

R^2 = P^2 + Q^2 + 2PQ cos(theta)
R^2 = 3^2 + 4^2 + 2 x 3 x 4 x cos 60
cos 60 = 1/2, so R^2 = 25 + 24 = 49
R = 7 N
""",
}


LINE = re.compile(r"Line (\d+) is where it goes wrong")
NONE = re.compile(r"No wrong line found")
BLOCK = re.compile(r"BLOCKED")


def write_cases():
    for name, body in CASES.items():
        with open(os.path.join(HERE, name), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(body)
    return len(CASES)


def expected(path):
    """"l3" -> 3, "ok" -> None, "blocked" -> "blocked"."""
    tail = os.path.basename(path)[:-4].rsplit("-", 1)[-1]
    if tail == "ok":
        return None
    if tail == "blocked":
        return "blocked"
    return int(tail.lstrip("l"))


def run(path):
    out = subprocess.run([sys.executable, os.path.join(ROOT, "firstwrong.py"), path],
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
    if isinstance(got, str) and got.startswith("unparsed"):
        return "unparsed"
    if want == "blocked":
        return "exact" if got == "blocked" else "MISSED BLOCK"
    if got == "blocked":
        return "blocked instead"
    if want is None:
        return "exact" if got is None else "FALSE POSITIVE"
    if got is None:
        return "false negative"
    return "exact" if got == want else "wrong line"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--write", action="store_true", help="write cases, do not run")
    args = ap.parse_args()

    n = write_cases()
    if args.write:
        print("wrote %d cases to %s" % (n, HERE))
        return 0

    files = sorted(f for f in glob.glob(os.path.join(HERE, "*.txt"))
                   if args.only in os.path.basename(f))
    if not files:
        print("no cases matched")
        return 1

    print("running %d cases (~$%.2f)..." % (len(files), len(files) * COST_PER_CASE))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, files))

    tally = {}
    print()
    print("  %-36s %-9s %-10s %s" % ("case", "expect", "got", "verdict"))
    print("  " + "-" * 78)
    for path, got in zip(files, results):
        want = expected(path)
        v = verdict(want, got)
        tally[v] = tally.get(v, 0) + 1
        show = "none" if got is None else str(got)
        wshow = "none" if want is None else (want if want == "blocked" else "l%d" % want)
        print("  %-36s %-9s %-10s %s" % (os.path.basename(path)[:-4], wshow,
                                         show[:10], v))
    print()
    for k in sorted(tally):
        print("  %-20s : %d" % (k, tally[k]))
    print()
    print("  run cost: about $%.2f" % (len(files) * COST_PER_CASE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
