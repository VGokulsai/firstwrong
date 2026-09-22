# firstwrong

Tells you the first line of your working that is wrong. Nothing else: no
solution, no next step, no hint about what is wrong with the line.

```
py -3 firstwrong.py working.txt
```

```
Line 4 is where it goes wrong.
Everything up to line 3 is correct.

    4. 3x = 29
```

You go back and look at line 4 yourself, which is the part that makes it stick.
Standard library only. It calls the `claude` CLI once per check.

## What it is not

- Not a solver. It never prints an answer, an explanation, or a hint.
- Not a grader of the question. It checks that each line follows from the last.
  It does not check that you answered the question that was asked.
- Not an OCR tool. You type the working; no photo of handwriting.
- Not deterministic. One model call per check, so the same input can give a
  different verdict twice. Treat any single result as a prompt to look, not a
  proof.

## The refusal is structural, not a promise

The model solves the problem internally, because it has to in order to compare.
But `ask()` reads exactly three values out of the reply: `solvable`, a line
number, and a confidence flag. Any solution, explanation, or hint the model
returns sits in the discarded data and goes out of scope unread. There is no
code path anywhere that prints it. A prompt asking the model not to explain is
a request; not reading the field is a guarantee.

## It never says "looks fine"

- Cannot solve it -> `BLOCKED`. That is not the same as your working being
  correct.
- No wrong line -> each line follows from the one before, not that the answer
  is what the question wanted.
- Points outside the working -> `BLOCKED`. An answer that does not fit the
  working is not an answer.
- Low confidence -> says so, and tells you to check it yourself.

## Format

Problem, a blank line, then your working, one step per line.

```
Solve 3x + 7 = 22 for x

3x + 7 = 22
3x = 22 + 7
3x = 29
x = 29/3
```

`--example` writes that file. `--check` tests that `claude` is present. Working
over 200 lines or 20,000 characters is refused rather than truncated, because a
silent cut would renumber the lines and point at the wrong one.

## Tests

The cases are graded by running the model live, so a run costs money (about
$0.002 per case) and results vary run to run.

```
py -3 score.py               25 topic cases in tests/cases/
py -3 tests/hard/hard.py     19 cases written to break it
```

The 19 adversarial cases are 10 with a planted error on a known line, 6 correct
workings written to look wrong, and 3 that are unanswerable and must come back
`BLOCKED`. Each case's expectation and reasoning is the comment above it,
written before anything ran and not edited after. The correct-working and
unanswerable cases matter most: a checker that invents an error in correct
work, or passes an unanswerable problem as clean, is worse than no checker.

The one boundary it failed at was deciding whether a problem is answerable at
all. A problem with an impossible premise came back clean because the model
treated "I can prove this has no solution" as having solved it. That is now
spelled out in the prompt.

Standard library only. The `claude` call runs with the flags that strip
CLAUDE.md, skills, and plugins out of the request.
