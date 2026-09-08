# firstwrong

Where your working goes wrong. Not what the answer is.

```
py -3 firstwrong.py working.txt
```

```
Line 4 is where it goes wrong.
Everything up to line 3 is correct.

    4. 3x = 29
```

No solution. No next step. No hint about what is wrong with line 4. You go
back and look at line 4 yourself, which is the part that makes it stick.

## Why it refuses

Every homework tool solves the problem for you, which is why using one leaves
you no better at the subject. Being handed a correct solution teaches you
nothing - you already know that from every worked example you have read and
forgotten. Finding your own mistake at a known location is different.

## The refusal is structural, not a promise

The model does solve the problem internally, because it has to in order to
compare. But `ask()` reads exactly three values out of the reply: solvable, a
line number, and a confidence flag. A solution, an explanation or a hint may
well be in the response - it goes out of scope unread, and there is no code
path anywhere that prints it.

A prompt asking the model not to explain is a request. Not reading the field
is a guarantee.

## It never says "looks fine"

- **Cannot solve it** -> BLOCKED. "That is not the same as your working being
  correct."
- **No wrong line** -> "each line follows from the one before, not that the
  answer is what the question wanted." Correct steps to the wrong question is
  still wrong, and this tool cannot tell you that.
- **Points outside the working** -> BLOCKED. An answer that does not fit the
  working is not an answer.
- **Low confidence** -> says so, and tells you to check it yourself.

## Format

Problem, blank line, then your working, one step per line.

```
Solve 3x + 7 = 22 for x

3x + 7 = 22
3x = 22 + 7
3x = 29
x = 29/3
```

`--example` writes that file. `--check` tests the prerequisites.

## Tested

| case | expected | got |
|---|---|---|
| sign error on line 2 | line 2 | line 2 |
| physics, dropped the square in (1/2)mv^2 | line 3 | line 3 |
| entirely correct working | no wrong line | no wrong line |
| valid but unusual route (sum and product of roots) | no wrong line | no wrong line |

The last two matter most. A checker that invents an error in correct working,
or that punishes a valid shortcut for not being the textbook route, is worse
than no checker.

## Limits

- You type the working. No photo of handwriting - OCR on handwritten maths is
  unreliable and would fail silently, which is the one failure mode this
  codebase refuses.
- It checks that each line follows from the last. It does not check that you
  answered the question that was asked.
- One model call per check, on the Claude subscription with the flags that
  strip CLAUDE.md, skills and plugins out of the request.

Standard library only.
