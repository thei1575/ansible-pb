"""Reading the resolved inventory.

`load_inventory` shells out to `ansible-inventory --list`. Rather than install
Ansible, these tests put a stub of that name on `PATH` and check what pb makes
of its output — including the shapes that break naive parsing.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from pb import meta

INVENTORY = {
    "_meta": {
        "hostvars": {
            "web01": {"ansible_host": "10.0.0.11", "mysql_password": "hunter2"},
            "web02": {"ansible_host": "10.0.0.12"},
            "stg01": {"ansible_host": "10.0.0.21"},
        }
    },
    "all": {"children": ["web", "staging", "ungrouped"]},
    "web": {"hosts": ["web02", "web01"]},
    "staging": {"hosts": ["stg01"]},
    # A group with no hosts of its own, and a non-dict entry: neither is a group
    # worth listing.
    "empty": {"children": ["web"]},
    "ungrouped": {},
}


@pytest.fixture
def fake_ansible_inventory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Put a stub `ansible-inventory` first on PATH. Returns a setter."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "ansible-inventory"
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")

    def install(stdout: str, code: int = 0) -> None:
        script.write_text(f"#!/bin/sh\ncat <<'JSON'\n{stdout}\nJSON\nexit {code}\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

    return install


def test_load_inventory_reads_hosts_addresses_and_groups(
    repo: meta.Repo, fake_ansible_inventory
) -> None:
    fake_ansible_inventory(json.dumps(INVENTORY))
    inv = meta.load_inventory(repo)

    assert inv.error == ""
    assert [h.name for h in inv.hosts] == ["stg01", "web01", "web02"]
    web01 = next(h for h in inv.hosts if h.name == "web01")
    assert web01.address == "10.0.0.11"
    assert web01.groups == ["web"]


def test_load_inventory_skips_all_and_childless_groups(
    repo: meta.Repo, fake_ansible_inventory
) -> None:
    fake_ansible_inventory(json.dumps(INVENTORY))
    inv = meta.load_inventory(repo)
    assert list(inv.groups) == ["staging", "web"]
    assert inv.groups["web"] == ["web01", "web02"]


def test_hostvars_still_carry_the_secret_that_redact_is_for(
    repo: meta.Repo, fake_ansible_inventory
) -> None:
    """ansible-inventory decrypts vaults; masking is the caller's job."""
    fake_ansible_inventory(json.dumps(INVENTORY))
    web01 = next(h for h in meta.load_inventory(repo).hosts if h.name == "web01")
    assert web01.vars["mysql_password"] == "hunter2"
    assert meta.redact(web01.vars)["mysql_password"] == meta.MASK


def test_load_inventory_reports_a_failure_instead_of_raising(
    repo: meta.Repo, fake_ansible_inventory
) -> None:
    fake_ansible_inventory("ERROR! Attempting to decrypt but no vault secrets found", code=1)
    inv = meta.load_inventory(repo)
    assert inv.hosts == []
    assert "no vault secrets found" in inv.error


def test_load_inventory_repeats_what_ansible_said_when_there_is_no_json(
    repo: meta.Repo, fake_ansible_inventory
) -> None:
    """Ansible's own words beat "pb could not parse ansible's output"."""
    fake_ansible_inventory("[WARNING]: Unable to parse inventories/typo as an inventory source")
    inv = meta.load_inventory(repo)
    assert inv.hosts == []
    assert "Unable to parse inventories/typo" in inv.error


def test_a_warning_printed_before_the_json_does_not_break_parsing(
    repo: meta.Repo, fake_ansible_inventory
) -> None:
    """capture() merges stderr into stdout, and ansible warns on stderr — so
    the JSON is usually not the whole output."""
    fake_ansible_inventory(
        "[WARNING]: Found both group and host with same name: web\n" + json.dumps(INVENTORY)
    )
    inv = meta.load_inventory(repo)
    assert inv.error == ""
    assert [h.name for h in inv.hosts] == ["stg01", "web01", "web02"]
    assert "same name: web" in inv.warning


def test_a_warning_printed_after_the_json_is_also_tolerated(
    repo: meta.Repo, fake_ansible_inventory
) -> None:
    fake_ansible_inventory(json.dumps(INVENTORY) + "\n[WARNING]: something afterwards")
    inv = meta.load_inventory(repo)
    assert inv.error == ""
    assert len(inv.hosts) == 3
    assert "something afterwards" in inv.warning


def test_a_clean_run_carries_no_warning(repo: meta.Repo, fake_ansible_inventory) -> None:
    fake_ansible_inventory(json.dumps(INVENTORY))
    assert meta.load_inventory(repo).warning == ""


def test_an_empty_inventory_with_a_warning_explains_itself(
    repo: meta.Repo, fake_ansible_inventory
) -> None:
    """This is the case that used to look like a pb bug rather than a config one."""
    empty = {"_meta": {"hostvars": {}}, "all": {"children": ["ungrouped"]}}
    fake_ansible_inventory(
        "[WARNING]: No inventory was parsed, only implicit localhost is available\n"
        + json.dumps(empty)
    )
    inv = meta.load_inventory(repo)
    assert inv.hosts == []
    assert inv.error == ""
    assert "No inventory was parsed" in inv.warning


def test_load_inventory_reports_a_missing_binary(repo: meta.Repo, monkeypatch) -> None:
    monkeypatch.setenv("PATH", "")
    inv = meta.load_inventory(repo)
    assert "not found on PATH" in inv.error
