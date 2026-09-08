"""Where your working goes wrong. Not what the answer is.

Every homework tool solves the problem for you, which is why using one leaves
you no better at the subject. This does the opposite: you type your working,
and the only thing it ever tells you is the first line that is wrong.

    Line 4 is where it goes wrong.
    Everything up to line 3 is correct.

No solution. No next step. No hint about what is wrong with line 4. You go
back and look at line 4 yourself, which is the part that makes it stick.

The model does solve the problem internally, because it has to in order to
compare. But the only value this code ever reads out of the reply is one
integer. Any solution, explanation or hint the model returns is dropped here,
unread. The answer is structurally unreachable, not politely withheld - the
same reason a mailbox opened readonly cannot delete a message.

    py -3 firstwrong.py working.txt      check a file
    py -3 firstwrong.py                  paste it, then ctrl-Z and enter
    py -3 firstwrong.py --example        write an example file to start from
    py -3 firstwrong.py --check          is everything this needs present

The file is the problem, a blank line, then your working one step per line:

    Solve 3x + 7 = 22 for x

    3x + 7 = 22
    3x = 22 + 7
    3x = 29
    x = 29/3
"""

import argparse
import json
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODEL = os.environ.get("FIRSTWRONG_MODEL", "claude-sonnet-5")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# The system prompt asks for one integer. The code below enforces it by
# reading nothing else, because a prompt is a request and this needs a
# guarantee.
SYSTEM = (
    "You check a student's working for the FIRST line that is mathematically "
    "or logically wrong. Solve it yourself to compare, but you are never "
    "asked for your solution and it will not be read.\n\n"
    "Reply with one JSON object and nothing else:\n"
    '{"solvable": true|false, "first_wrong_line": <1-based line number or '
    'null if every line is correct>, "confident": true|false}\n\n'
    "first_wrong_line is the first line whose content does not follow from "
    "the lines before it and the problem. A line that is merely inelegant, "
    "unsimplified, or a different valid route is NOT wrong. If you cannot "
    "solve the problem yourself, set solvable false; do not guess a line. "
    "Do not include a solution, an explanation, a hint, or any other field."
)

EXAMPLE = """Solve 3x + 7 = 22 for x

3x + 7 = 22
3x = 22 + 7
3x = 29
x = 29/3
"""


def have(command):
    try:
        subprocess.run([command, "-v"], capture_output=True, timeout=10,
                       creationflags=NO_WINDOW)
        return True
    except Exception:
        return False


def split_input(text):
    """(problem, [working lines]). The first block is the problem; everything
    after the first blank line is the working, one step per line."""
    blocks = text.replace("\r\n", "\n").split("\n\n", 1)
    if len(blocks) == 1:
        lines = [l for l in blocks[0].split("\n") if l.strip()]
        return (lines[0] if lines else ""), lines[1:]
    problem = " ".join(blocks[0].split())
    working = [l.strip() for l in blocks[1].split("\n") if l.strip()]
    return problem, working


def carve(text):
    """The first balanced JSON object in a reply."""
    text = (text or "").strip()
    start = text.find("{")
    if start < 0:
        return None
    depth, in_string, escaped = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


def ask(problem, working):
    """Returns (solvable, first_wrong_line, confident, problem_text).

    Everything else in the reply is discarded here and never returned, so no
    caller further up can print it even by accident.
    """
    prompt = ["PROBLEM", problem, "", "WORKING, one line per step:"]
    for n, line in enumerate(working, 1):
        prompt.append("%d. %s" % (n, line))
    prompt.append("")
    prompt.append("Which is the first line that is wrong? JSON only.")

    cmd = ["claude", "-p", "--model", MODEL, "--output-format", "json",
           "--setting-sources", "", "--tools", "", "--strict-mcp-config",
           "--system-prompt", SYSTEM]
    try:
        out = subprocess.run(cmd, input="\n".join(prompt), capture_output=True,
                             timeout=300, creationflags=NO_WINDOW,
                             encoding="utf-8", errors="replace")
    except Exception as exc:
        return None, None, None, "could not run claude: %s" % exc

    envelope = carve(out.stdout)
    if envelope is None:
        return None, None, None, ("claude returned no envelope: %s"
                                  % (out.stderr or "")[:160])
    if envelope.get("is_error"):
        return None, None, None, str(envelope.get("result") or "claude errored")

    data = carve(envelope.get("result") or "")
    if data is None:
        return None, None, None, "the reply was not JSON"

    # THIS is the product. Three values are read; a "solution", "explanation",
    # "hint" or anything else the model decided to include sits in `data` and
    # goes out of scope unread. There is no code path that prints it.
    solvable = bool(data.get("solvable"))
    line = data.get("first_wrong_line")
    confident = bool(data.get("confident"))
    try:
        line = int(line) if line is not None else None
    except Exception:
        line = None
    return solvable, line, confident, ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--example", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.check:
        print()
        print("  claude : %s" % ("found" if have("claude") else "MISSING"))
        print("  model  : %s" % MODEL)
        print()
        return 0

    if args.example:
        with open("working.txt", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(EXAMPLE)
        print("  wrote working.txt - edit it, then: py -3 firstwrong.py working.txt")
        return 0

    if args.file:
        if not os.path.isfile(args.file):
            print("  no file at %s" % args.file, file=sys.stderr)
            return 2
        with open(args.file, encoding="utf-8") as fh:
            raw = fh.read()
    else:
        print("  Paste the problem, a blank line, then your working.")
        print("  Finish with ctrl-Z then enter.\n")
        raw = sys.stdin.read()

    problem, working = split_input(raw)
    if not problem or not working:
        print("\n  Need a problem, a blank line, then at least one line of"
              " working.\n  Run --example to see the shape.\n", file=sys.stderr)
        return 2

    solvable, line, confident, problem_text = ask(problem, working)

    print()
    if problem_text:
        print("  BLOCKED: %s" % problem_text, file=sys.stderr)
        print("  Nothing was checked, so nothing here says your working is"
              " right.\n", file=sys.stderr)
        return 2

    if not solvable:
        # Never "looks fine". An unsolved problem is an unchecked one.
        print("  BLOCKED: could not solve this problem, so it could not be"
              " checked.")
        print("  That is not the same as your working being correct.\n")
        return 2

    if line is None:
        print("  No wrong line found in %d lines." % len(working))
        print("  That means each line follows from the one before, not that"
              " the")
        print("  answer is what the question wanted.\n")
        return 0

    if line < 1 or line > len(working):
        print("  BLOCKED: it pointed at line %d, and there are %d lines."
              % (line, len(working)))
        print("  An answer that does not fit the working is not an answer.\n")
        return 2

    print("  Line %d is where it goes wrong." % line)
    if line > 1:
        print("  Everything up to line %d is correct." % (line - 1))
    else:
        print("  The very first line.")
    print()
    print("      %d. %s" % (line, working[line - 1]))
    print()
    if not confident:
        print("  Low confidence on this one - check it yourself before"
              " believing it.")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
