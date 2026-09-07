# Security policy

## Reporting a vulnerability

Please do not open a public issue. Report it privately through GitHub's
[private vulnerability reporting][advisories] on this repository, or email
**theis@oz1tnj.dk**.

Include what you did, what pb did, and what you expected. I will acknowledge
within a week and tell you whether I consider it a vulnerability and what the
fix looks like.

[advisories]: https://github.com/thei1575/ansible-pb/security/advisories/new

## Supported versions

pb is pre-1.0. Fixes land on `main`; there are no maintained release branches.

## What pb touches, and what that means for you

pb is a console over your own Ansible repository. It runs on your machine as
you, with your credentials, and it deliberately has a lot of reach. Things
worth knowing:

* **pb runs Ansible as you.** It shells out to `ansible-playbook`,
  `ansible-inventory` and `ansible-vault` on your `PATH`, in your repo, with
  your environment. Anything those can do, pb can do. The exact command is
  always shown before it runs — read it.
* **`ansible-inventory` decrypts your vaults.** Resolving inventory variables
  means the plaintext of every group vault passes through pb's memory. The
  Inventory tab masks anything credential-shaped (`*_password`, `*_token`,
  `*_key`, `secret`, `salt`, …) until you press `R`, but the mask is a
  screen-level courtesy, not a boundary. Do not screen-share the Inventory tab
  with values revealed.
* **Run records contain full Ansible output.** Every run is written to
  `.pb/runs/` in your repo — the command, the recap, and the complete captured
  output, which can include anything a task printed. Add `.pb/` to your repo's
  `.gitignore`. pb prunes to the last 300 runs and never deletes the
  directory itself.
* **The SSH probe is read-only.** The Status tab pipes a fixed shell script to
  `ssh <host>` on stdin. It only reads (`uname`, `df`, `systemctl
  list-units`, `docker ps`, `openssl x509 -enddate`) and changes nothing. It
  uses your existing SSH config, keys and agent; pb never handles a password.
  It connects with `BatchMode=yes` and `StrictHostKeyChecking=accept-new`, so a
  host key pb has not seen before is accepted and pinned on the first probe
  rather than prompting. These are passed as `-o` flags, which take precedence
  over `~/.ssh/config`, so a stricter setting there will not override them — if
  that trade-off does not suit you, please open an issue.
* **Vault edits go through `ansible-vault`.** pb writes an encrypted file only
  by invoking `ansible-vault` itself. It reads your vault password from the
  repo's `.vault_pass` the same way Ansible does — keep that file `0600` and
  gitignored. pb never stores or transmits it.
* **pb makes no network connections of its own.** No telemetry, no update
  check, no outbound anything. The only traffic is Ansible's and SSH's.

## Out of scope

* A masked value being recoverable by someone who already has your terminal,
  your repo and your vault password. The mask guards against shoulder-surfing
  and screen-sharing, nothing more.
* Anything Ansible itself does with a playbook you chose to run.
* Local file permissions on `.vault_pass` or `.pb/` — pb honours your umask;
  setting them correctly is yours.
