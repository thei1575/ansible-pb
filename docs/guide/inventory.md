# Inventory

<kbd>2</kbd>

Hosts, groups, and fully resolved variables come from
`ansible-inventory --list`, including group inheritance, `host_vars`, and
decrypted vault data.

The pane on the right shows the selected host: its address, its groups, and its
resolved variables with anything credential-shaped masked.

## Verbs

<div class="pb-keys" markdown>

| Key | Does | Runs |
|---|---|---|
| <kbd>p</kbd> | Ping the host | `ansible <host> -m ping` |
| <kbd>f</kbd> | Gather facts | `ansible <host> -m setup` |
| <kbd>i</kbd> | Resolved vars, as JSON | nothing - already loaded |
| <kbd>s</kbd> | SSH into the host | `ssh <ansible_user>@<address>` |
| <kbd>R</kbd> | Reveal / re-mask secrets | nothing |

</div>

<kbd>p</kbd> and <kbd>f</kbd> open a normal run view, so their output is
streamed, saveable, and [recorded](history.md) like any other run.

<kbd>s</kbd> leaves the TUI for a real terminal and returns to pb when the
session ends. It uses `ansible_user` where the host defines one and `root`
otherwise, and `ansible_host` as the address where there is one, falling back to
the inventory name.

## Secrets are masked by default

`ansible-inventory --list` decrypts the vaults in order to resolve variables.
That means the plaintext of every group vault passes through pb, and would
otherwise be sitting in a table.

So pb masks it. Any variable whose **name** looks like a credential is replaced
with `•••• hidden ••••` until you press <kbd>R</kbd>:

```
pass, password, passphrase, secret, token, api_key, api-key,
apikey, <anything>_key, key, salt, credential, private_key,
private-key, auth
```

The match is case-insensitive and substring-based, so `db_password`,
`ANSIBLE_VAULT_TOKEN` and `letsencrypt_private_key` are all caught.

Only **non-empty strings** are masked. `common_disable_ssh_passwords: true`
matches the name pattern, but hiding a boolean helps nobody, so pb leaves
numbers, booleans, lists and dicts visible.

<kbd>R</kbd> toggles revealing for the whole tab, and pb warns you on screen
when you turn it on. <kbd>i</kbd> respects the current setting and says which
mode it is in in its title: `web01 - resolved vars (secrets masked)`.

!!! danger "The mask is a courtesy, not a boundary"

    It guards against shoulder-surfing and screen-sharing. Anyone with your
    terminal, your repo and your vault password can read the values anyway -
    that is what the [Vault](vault.md) tab is for. Do not screen-share the
    Inventory tab with values revealed. See [Security](../project/security.md).

## When there are no hosts

`ansible-inventory` writes warnings to stderr, and pb merges stderr into stdout
so nothing is lost. That used to make a warning look like a parse failure, so pb
now finds the JSON inside the output, keeps whatever was printed around it, and
shows it.

The practical effect: "no hosts" tells you *why*.

- A **warning** - an unparsable file in the inventory directory, a plugin that
  declined - is shown as a warning in Doctor and the hosts pb did find are
  still listed.
- A real **error** - a missing inventory path, a vault it cannot decrypt - is
  shown as an error, with Ansible's own message.

If neither appears and the list is genuinely empty, the inventory pb is reading
is not the one you think it is. Check the inventory line in
[Doctor](doctor.md) and read
[Inventory resolution](../reference/inventory-resolution.md).

## Groups

The group list comes from the top level of `ansible-inventory --list`: every
group that has hosts of its own, sorted, with its members. Two things follow
from that, and both are deliberate:

- **`all` is not listed.** It is every host by definition, and the limit picker
  already offers `all` as its first choice.
- **A group that only has children is not listed either.** `--list` puts a host
  under the groups that name it directly, so a parent whose membership is
  entirely inherited has no `hosts` of its own to show.

Each host's own row names every group that lists it, which is the same
information read the other way round.

This group list is exactly what the <kbd>l</kbd> limit picker in
[Playbooks](playbooks.md) offers, which is why a limit chosen there always
resolves to something.
