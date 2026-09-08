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
    py -3 firstwrong.py "Solve 3x + 7 = 22 for x" "3x + 7 = 22" "3x = 29"
                                         problem first, then one step per argument
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
import re
import subprocess
import sys

# Textbook maths is pasted in as unicode; a console in cp1252 must not turn a
# square root sign into a traceback on either stream.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# Past this it is not homework, and a line number nobody can count to is not
# an answer. Refused rather than truncated: a silent cut would renumber the
# working and point at the wrong line.
MAX_LINES = 200
MAX_CHARS = 20000

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


def looks_like_path(word):
    """Was a lone argument meant as a file? Only used when no such file
    exists, to tell a typo'd path apart from a one-line problem."""
    return ("/" in word or os.sep in word
            or word.lower().endswith((".txt", ".md", ".text")))


def split_input(text):
    """(problem, [working lines]). The first block is the problem; everything
    after the first blank line is the working, one step per line."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # A "blank" line pasted out of an editor often carries a space or a tab.
    # Splitting on a literal "\n\n" misses it, and then the second line of the
    # problem becomes working line 1 and every reported number is off by one.
    blocks = re.split(r"\n[ \t]*\n", text, maxsplit=1)
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


def flag(value):
    """A JSON boolean, or the model's idea of one. The string "false" is a
    false, not a non-empty string; bool("false") being True would turn an
    unsolved problem into a clean sheet."""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


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
    solvable = flag(data.get("solvable"))
    confident = flag(data.get("confident"))
    if "first_wrong_line" not in data:
        return None, None, None, "the reply left the line number out"

    line = data.get("first_wrong_line")
    if isinstance(line, str) and line.strip().lower() in ("", "null", "none"):
        line = None
    if line is not None:
        # An unreadable line number is a failed check, and a failed check is
        # blocked. Falling back to None here would print "no wrong line" -
        # a pass - on a reply nobody could read. The bad value is deliberately
        # not echoed: the model may have put its explanation in this field.
        try:
            n = int(line.strip() if isinstance(line, str) else line)
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None, None, None, "it did not give a usable line number"
        # int(3.7) silently truncating to 3 would point at a line the model
        # did not name, and int(True) is 1.
        if isinstance(line, bool) or (isinstance(line, float) and n != line):
            return None, None, None, "it did not give a usable line number"
        line = n
    return solvable, line, confident, ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("words", nargs="*", metavar="FILE | PROBLEM STEP...",
                    help="a file, or the problem then one step per argument")
    ap.add_argument("--example", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.check:
        found = have("claude")
        print()
        print("  claude : %s" % ("found" if found else "MISSING"))
        print("  model  : %s" % MODEL)
        print()
        return 0 if found else 1

    if args.example:
        if os.path.exists("working.txt"):
            print("  working.txt already exists - not overwriting it.",
                  file=sys.stderr)
            return 2
        with open("working.txt", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(EXAMPLE)
        print("  wrote working.txt - edit it, then: py -3 firstwrong.py working.txt")
        return 0

    words = args.words
    if len(words) == 1 and (os.path.isfile(words[0]) or looks_like_path(words[0])):
        if not os.path.isfile(words[0]):
            # A mistyped path must say so. Silently checking it as a maths
            # problem would blame the working for a filename.
            print("  no file at %s" % words[0], file=sys.stderr)
            return 2
        # utf-8-sig eats the BOM Notepad writes; errors=replace keeps a
        # cp1252 textbook paste from ending as a traceback.
        with open(words[0], encoding="utf-8-sig", errors="replace") as fh:
            raw = fh.read()
    elif words:
        raw = words[0] + "\n\n" + "\n".join(words[1:])
    else:
        print("  Paste the problem, a blank line, then your working.")
        print("  Finish with ctrl-Z then enter.\n")
        raw = sys.stdin.read()

    problem, working = split_input(raw)
    if not problem or not working:
        print("\n  Need a problem, a blank line, then at least one line of"
              " working.\n  Run --example to see the shape.\n", file=sys.stderr)
        return 2

    size = sum(len(l) for l in working)
    if len(working) > MAX_LINES or size > MAX_CHARS:
        print("\n  BLOCKED: too much working - lines: %d, characters: %d."
              % (len(working), size), file=sys.stderr)
        print("  One problem at a time. Nothing was checked.\n", file=sys.stderr)
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
        print("  answer is what the question wanted.")
    else:
        if line < 1 or line > len(working):
            print("  BLOCKED: it pointed at line %d, and there are %d lines."
                  % (line, len(working)))
            print("  An answer that does not fit the working is not an"
                  " answer.\n")
            return 2

        print("  Line %d is where it goes wrong." % line)
        if line > 1:
            print("  Everything up to line %d is correct." % (line - 1))
        else:
            print("  The very first line.")
        print()
        print("      %d. %s" % (line, working[line - 1]))

    # An unconfident clean sheet is still unconfident. Warning only on a found
    # line was the same fail-as-pass in a quieter form.
    if not confident:
        print()
        print("  Low confidence on this one - check it yourself before"
              " believing it.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
