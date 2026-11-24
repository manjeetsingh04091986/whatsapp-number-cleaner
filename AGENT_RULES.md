# Overnight Test Agent rules

These rules apply to the scheduled "Overnight Test Agent" job. A human reviews and
merges every PR; the agent never merges.

## Scope
- Write or extend tests **only** under `tests/`. Do not edit `app.py`,
  `cleaner.py`, workflows, `requirements.txt`, or any other file.
- If you think the code has a bug, do not fix it. Write the test that shows the
  expected behaviour, mark it `@pytest.mark.xfail(reason="...")`, and describe
  the suspected bug in the PR.

## What makes a good test here
- Test **behaviour a user would care about**, not the current implementation.
  Examples: country-code handling, spaces/brackets/leading zeros, too-short
  numbers, repeated-digit junk numbers, Mobile vs Phone preference, summary stats.
- Every test needs a one-line docstring stating the rule it checks.
- Don't write tests that just repeat the code's logic or assert on internals.
- No network, no Jira, no Files.com, no Streamlit. Mock or avoid them.

## Data
- Use **made-up numbers only** (e.g. +44 7700 900123, the UK's reserved
  drama range, or obviously fake patterns). Never use real phone numbers, and
  never read files outside this repo.
- Never print, log, or commit secrets or environment variables.

## Process
1. Run `python -m pytest` first to see what exists. Don't break existing tests.
2. Pick **one** under-tested area. Keep the PR small: at most 1-2 test files,
   roughly 15 tests.
3. Run the new tests and confirm they pass. Run them twice to check they aren't flaky.
4. Branch name `ai-tests/YYYY-MM-DD`; commit only files under `tests/`.
5. Open one PR labelled `ai-tests`. The description must list: what area was
   covered, each business rule tested, anything xfailed, and the pytest result.
6. If tests can't be made to pass meaningfully, open no PR.
