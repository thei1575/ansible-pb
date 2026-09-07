# Plugins

<kbd>8</kbd>

pb is deliberately narrow, which leaves the things only your own
infrastructure cares about — a drift check, a change-ticket gate, a
notification on every apply — with nowhere to go. A plugin is where they go.

A plugin is a git repository pb clones and imports at start-up. It can add a
tab, add keys to a tab pb already has, add [Doctor](doctor.md) checks and
command-palette entries, edit or veto a command before it runs, react to a
finished run, and append to any detail pane or the status strip. It can also
**replace** what one of pb's own keys does.

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>i</kbd> | Install one from GitHub |
| <kbd>u</kbd> | Update the selected plugin |
| <kbd>e</kbd> | Enable or disable it |
| <kbd>r</kbd> | Remove it |
| <kbd>o</kbd> | Everything pb knows about it, including a load failure |

</div>

To write one, see [Writing a plugin](../reference/writing-plugins.md).

## What each row shows

| Column | Comes from |
|---|---|
| Plugin | the `name` in its `pb-plugin.toml` |
| Version | the `version` in the same file |
| State | `✔ loaded`, `• pending restart`, `disabled`, or `✘` and the stage it failed at |
| Where from | what you typed when you installed it, or the directory it is linked to |
| What it adds | its one-line `summary` |

The detail pane adds the ref and commit that are checked out, the directory it
lives in, and which hooks that plugin actually implements — the quickest
answer to "what is this thing doing to my pb".

## Installing

<kbd>i</kbd> asks for a source, then shows what it is about to clone and what
installing means before anything is fetched. The same thing from a shell:

```bash
pb plugin install owner/pb-terraform         # GitHub
pb plugin install owner/pb-terraform@v1.2.0  # pinned to a tag
pb plugin install owner/pb-terraform --ref abc123
pb plugin install git@github.internal:ops/pb-mine.git
pb plugin install https://gitlab.example/ops/pb-mine.git#v2
```

`owner/repo` means GitHub, because that is where pb plugins are published.
Anything with a scheme, an `scp`-style `git@host:path`, or a path to a local
repository is handed to `git` untouched, so a private mirror needs nothing
from pb.

A pinned install stays pinned: `pb plugin update` re-resolves the same ref
rather than drifting onto a branch. An unpinned one fast-forwards to the
remote's default branch.

## Why a restart

Installing, updating, enabling and removing all take effect the next time pb
starts. Plugin code is imported once, at start-up, and pb does not pretend it
can swap it under a live UI — a half-replaced action or a tab whose widgets
belong to a previous version of the code is worse than being told to restart.

The messages say so, and the state on the tab distinguishes `✔ loaded` from
`• pending restart` precisely so you can tell which version you are looking
at.

## When a plugin breaks

pb catches everything a plugin's hooks raise. The plugin is switched off for
the rest of the session, its tabs are removed, its replaced actions are handed
back to the built-ins, a notification names the hook that failed, and it
becomes a failed check on the [Doctor](doctor.md) tab. pb keeps running.

That is deliberate: a plugin should cost you that plugin, never your console.
<kbd>o</kbd> shows the traceback.

If pb misbehaves and you are not sure a plugin is to blame, start it without
any:

```bash
pb --no-plugins        # PB_NO_PLUGINS=1 does the same
```

A plugin that will not even import is faster to diagnose from a shell, which
prints the traceback without starting the TUI:

```bash
pb plugin doctor
```

## What installing one means

A plugin is Python running inside pb, with your permissions. It can read your
repo and your `.vault_pass`, change the `ansible` commands pb builds, and
replace what any key does. There is no sandbox, and pb does not pretend there
is one.

So pb makes the decision an explicit one:

- Installing asks first, and prints the URL it is about to clone. `--yes`
  skips the prompt; with no terminal to ask in, `pb plugin install` refuses
  rather than installing silently.
- **Nothing a plugin ships runs at install time.** The clone is a clone; the
  code is imported the next time pb starts.
- Every install records the exact commit. `pb plugin info <name>` shows it,
  and the checkout is an ordinary git repository, so `git log` in it tells the
  truth about what you are running.
- `pb plugin disable <name>` keeps a plugin installed but stops loading it.

Read a plugin before you install it, the way you would read a shell script
someone sent you. See also
[Security](https://github.com/thei1575/ansible-pb/blob/main/.github/SECURITY.md).

## Where they live

Under [pb's config directory](../reference/files.md#writes-in-your-home-directory),
not in your Ansible repo: which plugins you have installed is about your
machine, not about the repo you are pointing pb at.
