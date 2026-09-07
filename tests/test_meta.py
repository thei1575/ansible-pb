"""Repo discovery, playbook/role/vault parsing, and secret redaction."""

from __future__ import annotations

from pathlib import Path

import pytest

from pb import meta

# --- redaction -------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        "mysql_password",
        "PASSWORD",
        "passphrase",
        "vault_secret",
        "api_key",
        "api-key",
        "github_token",
        "ssh_private_key",
        "tls_key",
        "key",
        "password_salt",
        "basic_auth",
        "db_credential",
    ],
)
def test_is_secret_catches_credential_names(key: str) -> None:
    assert meta.is_secret(key)


@pytest.mark.parametrize(
    "key",
    ["common_user", "hostname", "ansible_host", "keyboard_layout", "monkey", "port"],
)
def test_is_secret_leaves_ordinary_names_alone(key: str) -> None:
    assert not meta.is_secret(key)


def test_redact_masks_secret_strings_only() -> None:
    out = meta.redact(
        {
            "mysql_password": "hunter2",
            "common_user": "deploy",
            # Named like a secret, but a boolean: hiding it helps nobody.
            "common_disable_ssh_passwords": True,
            # Named like a secret, but empty: nothing to hide.
            "backup_token": "",
            "port_count": 3,
        }
    )
    assert out["mysql_password"] == meta.MASK
    assert out["common_user"] == "deploy"
    assert out["common_disable_ssh_passwords"] is True
    assert out["backup_token"] == ""
    assert out["port_count"] == 3


def test_redact_does_not_mutate_its_input() -> None:
    original = {"api_key": "abc"}
    meta.redact(original)
    assert original == {"api_key": "abc"}


# --- finding the root ------------------------------------------------


def test_find_root_walks_up_to_ansible_cfg(repo_root: Path) -> None:
    deep = repo_root / "roles" / "common" / "tasks"
    assert meta.find_root(deep) == repo_root.resolve()


def test_find_root_returns_start_when_there_is_no_cfg(tmp_path: Path) -> None:
    assert meta.find_root(tmp_path) == tmp_path.resolve()


def test_repo_paths_hang_off_the_root(repo: meta.Repo) -> None:
    assert repo.playbooks_dir.is_dir()
    assert repo.roles_dir.is_dir()
    assert repo.inventory.is_file()
    assert repo.group_vars_dir.is_dir()
    assert repo.vault_pass_file.is_file()


# --- playbooks -------------------------------------------------------


def test_discover_playbooks_finds_only_yml(repo: meta.Repo) -> None:
    names = [p.name for p in meta.discover_playbooks(repo)]
    assert "notes" not in names
    assert set(names) == {"site", "base", "web", "reset", "broken"}


def test_discover_playbooks_puts_site_first_then_aggregates(repo: meta.Repo) -> None:
    found = meta.discover_playbooks(repo)
    assert found[0].name == "site"
    kinds = {p.name: p.kind for p in found}
    assert kinds["site"] == "aggregate"
    assert kinds["reset"] == "interactive"
    assert kinds["web"] == "play"


def test_aggregate_playbook_lists_its_imports_without_the_suffix(repo: meta.Repo) -> None:
    site = next(p for p in meta.discover_playbooks(repo) if p.name == "site")
    assert site.imports == ["base", "web"]
    assert site.targets == []


def test_summary_prefers_the_header_comment_and_drops_dividers(repo: meta.Repo) -> None:
    by_name = {p.name: p for p in meta.discover_playbooks(repo)}
    assert by_name["site"].summary == "Everything, in order."
    assert by_name["base"].summary == "Bring a fresh host up to the baseline."
    # No header comment, so it falls back to the first play's name.
    assert by_name["web"].summary == "Web servers"


def test_comma_separated_hosts_become_separate_targets(repo: meta.Repo) -> None:
    web = next(p for p in meta.discover_playbooks(repo) if p.name == "web")
    assert web.targets == ["web", "staging"]


def test_a_target_used_by_two_plays_is_named_once(repo: meta.Repo) -> None:
    base = next(p for p in meta.discover_playbooks(repo) if p.name == "base")
    assert base.targets == ["all"]


def test_roles_are_read_from_both_shorthand_and_mapping_form(repo: meta.Repo) -> None:
    base = next(p for p in meta.discover_playbooks(repo) if p.name == "base")
    assert base.roles == ["common", "hardening", "common"]


def test_a_playbook_that_does_not_parse_is_still_listed(repo: meta.Repo) -> None:
    """A YAML error is the user's to fix; pb must not fall over on it."""
    broken = next(p for p in meta.discover_playbooks(repo) if p.name == "broken")
    assert broken.summary == "This one does not parse."
    assert broken.targets == []
    assert broken.roles == []


def test_tags_start_unlooked_up(repo: meta.Repo) -> None:
    """`None` means "not asked yet"; an empty list would mean "has no tags"."""
    assert all(p.tags is None for p in meta.discover_playbooks(repo))


# --- roles -----------------------------------------------------------


def test_discover_roles_counts_tasks_and_names_the_parts(repo: meta.Repo) -> None:
    roles = {r.name: r for r in meta.discover_roles(repo, meta.discover_playbooks(repo))}
    assert roles["common"].tasks == 2
    assert roles["common"].parts == ["defaults", "handlers"]
    assert roles["nginx"].tasks == 1
    assert roles["nginx"].parts == []


def test_discover_roles_reports_which_playbooks_use_each(repo: meta.Repo) -> None:
    roles = {r.name: r for r in meta.discover_roles(repo, meta.discover_playbooks(repo))}
    # base.yml uses common in two plays; it should be credited once.
    assert roles["common"].used_by == ["base", "reset"]
    assert roles["nginx"].used_by == ["web"]
    assert roles["empty"].used_by == []


def test_an_unused_role_directory_is_still_a_role(repo: meta.Repo) -> None:
    roles = {r.name: r for r in meta.discover_roles(repo, [])}
    assert roles["empty"].tasks == 0
    assert roles["empty"].parts == []


# --- vaults ----------------------------------------------------------


def test_discover_vaults_flags_an_unencrypted_file(repo: meta.Repo) -> None:
    vaults = {v.group: v for v in meta.discover_vaults(repo)}
    assert vaults["all"].encrypted is True
    assert vaults["web"].encrypted is False
    assert vaults["web"].size > 0


def test_discover_vaults_is_empty_when_there_are_none(tmp_path: Path) -> None:
    assert meta.discover_vaults(meta.Repo.discover(tmp_path)) == []


# --- shelling out ----------------------------------------------------


def test_capture_returns_127_for_a_missing_binary(tmp_path: Path) -> None:
    code, out = meta.capture(["pb-does-not-exist"], tmp_path)
    assert code == 127
    assert "not found on PATH" in out


def test_capture_returns_output_and_code(tmp_path: Path) -> None:
    code, out = meta.capture(["sh", "-c", "echo hello; exit 3"], tmp_path)
    assert code == 3
    assert out.strip() == "hello"


def test_capture_merges_stderr_into_the_output(tmp_path: Path) -> None:
    _, out = meta.capture(["sh", "-c", "echo oops >&2"], tmp_path)
    assert "oops" in out


def test_capture_times_out_rather_than_hanging(tmp_path: Path) -> None:
    code, out = meta.capture(["sh", "-c", "sleep 5"], tmp_path, timeout=1)
    assert code == 124
    assert "timed out" in out


# --- git -------------------------------------------------------------


def test_git_status_is_empty_outside_a_repo(repo: meta.Repo) -> None:
    branch, dirty = meta.git_status(repo)
    assert branch == ""
    assert dirty == 0


def test_git_status_reports_the_branch_and_the_dirty_count(git_repo: meta.Repo) -> None:
    branch, dirty = meta.git_status(git_repo)
    assert branch == "main"
    assert dirty == 1


def test_changed_paths_names_the_edited_file(git_repo: meta.Repo) -> None:
    assert "playbooks/web.yml" in meta.changed_paths(git_repo)


def test_changed_paths_is_empty_outside_a_repo(repo: meta.Repo) -> None:
    assert meta.changed_paths(repo) == set()
