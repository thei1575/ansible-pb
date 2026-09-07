# Updating

Current pb releases are installed from a Git URL. A daily GitHub release check
provides version discovery and an installation command inside the application.

## Update dialog

When there is a newer release, pb opens this over whichever tab you were on:

```
 pb 0.2.0 is out - you are running 0.1.0

  ## [0.2.0] - 2026-09-07

  ### Added

  * …the changelog entries between the two versions…

 $ uv tool install --force git+https://github.com/thei1575/ansible-pb@v0.2.0

  [ Update now ]  [ Skip this version ]  [ Later ]

 skip never offers this version again · esc asks again tomorrow
```

| Answer | Does |
|---|---|
| **Update now** | Runs the command shown, then tells you to restart pb |
| **Skip this version** | That version is never offered again. A later one still is |
| **Later**, or <kbd>esc</kbd> | Closes. pb asks again on the next day's check |

<kbd>ctrl</kbd>+<kbd>u</kbd> checks on demand, ignoring both the once-a-day
interval and anything you skipped - it is how you get a skipped version back.

## The command it runs

pb works out how it was installed from where it lives, and builds the matching
command:

| Installed with | Command |
|---|---|
| `uv tool` | `uv tool install --force git+https://github.com/thei1575/ansible-pb@<tag>` |
| `pipx` | `pipx install --force git+https://github.com/thei1575/ansible-pb@<tag>` |
| `pip` | `<this python> -m pip install --upgrade git+https://github.com/thei1575/ansible-pb@<tag>` |
| a source checkout | *nothing* - pb names the directory and leaves it to `git pull` |

You always see the whole command before it runs, the same as
[every other command pb builds](../guide/playbooks.md). A checkout installed
with `pip install -e` is never installed over: **Update now** is disabled and pb
tells you where the checkout is instead.

!!! note "Why the tag is pinned"

    `uv tool upgrade` on a package installed from a git URL keeps the ref it was
    installed with, so it would report success and change nothing. Pinning the
    tag is what actually moves you.

The new pb is on disk as soon as the command finishes, but the running process
is still the old one - a running Python cannot swap out the package it imported.
pb says so rather than pretending otherwise: quit and start it again.

If the install fails, pb shows you the command and its complete output instead
of claiming success.

## Where the changelog comes from

The release notes on the GitHub release, when there are any. Failing that, pb
reads `CHANGELOG.md` from the repository and shows every entry between the
version you are running and the one on offer - so what you are looking at is
what you would be getting, not just the newest entry. `## [Unreleased]` is left
out: it is not in the release.

## Turning it off

```bash
pb --no-update-check
export PB_NO_UPDATE_CHECK=1     # for every invocation
```

Either stops pb going to look on its own. <kbd>ctrl</kbd>+<kbd>u</kbd> still
works - the opt-out means "do not go looking", not "never".

## Network request

This is the only network connection pb makes on its own. Everything else you
see pb do is Ansible's traffic or SSH's.

| When | Request |
|---|---|
| At most once a day at startup, and on <kbd>ctrl</kbd>+<kbd>u</kbd> | `GET https://api.github.com/repos/thei1575/ansible-pb/releases/latest`, falling back to `/tags` |
| Only when there is a newer version, and the release has no notes | `GET https://raw.githubusercontent.com/thei1575/ansible-pb/<tag>/CHANGELOG.md` |

Both are unauthenticated and anonymous. Nothing about you, your repository, your
inventory or your hosts is sent. The only header that identifies anything is a
`pb/<version>` User-Agent, which GitHub requires of API clients. There is no
telemetry, and pb reports nothing about a check to anyone.

The request has a six-second timeout and every failure is silent: no network, a
proxy in the way, or GitHub rate-limiting an office full of unauthenticated
callers all mean pb starts as usual and tries again tomorrow.
<kbd>ctrl</kbd>+<kbd>u</kbd> says so out loud, since you asked.

## Local update state

`~/.config/pb/update.json`, described in
[Files pb touches](files.md#configpbupdatejson). Two keys: when pb last
looked, and which version you skipped. Delete it and pb starts over.

Installing a version successfully clears the skip - a version you installed is
not a version you declined.
