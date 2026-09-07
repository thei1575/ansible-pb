## What this changes

<!-- One or two sentences, from the user's point of view. -->

## Why

<!-- Link the issue if there is one: Fixes #123 -->

## How you tested it

<!-- Which Ansible repo did you run it against? What did you try? -->

## Checklist

- [ ] `ruff check .` passes
- [ ] `pytest` passes
- [ ] Anything that shells out runs in a worker thread, not on the UI thread
- [ ] Any new command is shown to the user before it runs
- [ ] Any new view over inventory data goes through `meta.redact()`
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`, if the change is
      user-visible
