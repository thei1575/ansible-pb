"""Where pb decides the inventory is.

pb has to agree with ansible about which inventory it is looking at, or the
host list it shows before an apply is a lie. The precedence mirrors ansible's
own: -i, then $ANSIBLE_INVENTORY, then ansible.cfg - and only then does pb
guess.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pb import meta


def _repo(root: Path, cfg: str = "[defaults]\n") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "ansible.cfg").write_text(cfg)
    return root


# --- precedence ------------------------------------------------------


def test_the_flag_wins_over_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, "[defaults]\ninventory = inventories/production\n")
    monkeypatch.setenv("ANSIBLE_INVENTORY", "inventories/staging")
    repo = meta.Repo.discover(root, "inventories/dev")
    assert repo.inventory == root / "inventories/dev"
    assert repo.inventory_origin == "--inventory"


def test_the_environment_wins_over_ansible_cfg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, "[defaults]\ninventory = inventories/production\n")
    monkeypatch.setenv("ANSIBLE_INVENTORY", "inventories/staging")
    repo = meta.Repo.discover(root)
    assert repo.inventory == root / "inventories/staging"
    assert repo.inventory_origin == "ANSIBLE_INVENTORY"


def test_ansible_cfg_is_read_when_nothing_overrides_it(tmp_path: Path) -> None:
    root = _repo(tmp_path, "[defaults]\ninventory = inventories/production/hosts.yml\n")
    repo = meta.Repo.discover(root)
    assert repo.inventory == root / "inventories/production/hosts.yml"
    assert repo.inventory_origin == "ansible.cfg"


def test_a_repo_that_names_no_inventory_is_searched(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "inventory").mkdir()
    repo = meta.Repo.discover(root)
    assert repo.inventory == root / "inventory"
    assert repo.inventory_origin == "found"


def test_the_search_prefers_the_layout_pb_used_to_assume(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "inventory").mkdir()
    (root / "inventories" / "production").mkdir(parents=True)
    assert meta.Repo.discover(root).inventory == root / "inventories/production"


def test_an_environment_with_any_name_at_all_is_found(tmp_path: Path) -> None:
    """The whole point: a repo that does not call it `production` still works."""
    root = _repo(tmp_path)
    (root / "inventories" / "staging").mkdir(parents=True)
    repo = meta.Repo.discover(root)
    assert repo.inventory == root / "inventories/staging"
    assert repo.inventory_origin == "found"
    assert repo.group_vars_dir == root / "inventories/staging/group_vars"


def test_production_wins_when_several_environments_exist(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    for env in ("aaa", "staging", "production", "zzz"):
        (root / "inventories" / env).mkdir(parents=True)
    assert meta.Repo.discover(root).inventory == root / "inventories/production"


def test_the_first_environment_is_taken_when_none_is_preferred(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    for env in ("staging", "dev"):
        (root / "inventories" / env).mkdir(parents=True)
    assert meta.Repo.discover(root).inventory == root / "inventories/dev"


def test_a_flat_inventories_directory_is_taken_whole(tmp_path: Path) -> None:
    """group_vars/ beside hosts.yml is a layout, not an environment."""
    root = _repo(tmp_path)
    (root / "inventories" / "group_vars").mkdir(parents=True)
    (root / "inventories" / "hosts.yml").write_text("all:\n")
    repo = meta.Repo.discover(root)
    assert repo.inventory == root / "inventories"
    assert repo.group_vars_dir == root / "inventories/group_vars"


def test_host_vars_is_not_mistaken_for_an_environment(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "inventory" / "host_vars").mkdir(parents=True)
    (root / "inventory" / "hosts.ini").write_text("[web]\nweb01\n")
    assert meta.Repo.discover(root).inventory == root / "inventory"


def test_a_directory_beats_a_root_level_hosts_file(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "hosts.yml").write_text("all:\n")
    (root / "inventories" / "dev").mkdir(parents=True)
    assert meta.Repo.discover(root).inventory == root / "inventories/dev"


def test_a_root_level_hosts_file_is_not_confused_with_a_directory(tmp_path: Path) -> None:
    """`inventory` as a *file* at the root, not a directory."""
    root = _repo(tmp_path)
    (root / "inventory.ini").write_text("[web]\nweb01\n")
    assert meta.Repo.discover(root).inventory == root / "inventory.ini"


def test_a_single_hosts_file_at_the_root_is_found(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "hosts.yml").write_text("all:\n")
    assert meta.Repo.discover(root).inventory == root / "hosts.yml"


def test_a_repo_with_nothing_to_find_keeps_the_historical_default(tmp_path: Path) -> None:
    repo = meta.Repo.discover(_repo(tmp_path))
    assert repo.inventory == tmp_path / "inventories/production"
    assert repo.inventory_origin == "default"


# --- how paths are read ----------------------------------------------


def test_an_absolute_path_is_taken_as_given(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere" / "hosts.yml"
    repo = meta.Repo.discover(_repo(tmp_path / "repo"), str(elsewhere))
    assert repo.inventory == elsewhere


def test_a_relative_path_hangs_off_the_repo_root(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert meta.Repo.discover(root, "inventories/dev").inventory == root / "inventories/dev"


def test_a_tilde_is_expanded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = meta.Repo.discover(_repo(tmp_path), "~/hosts.yml")
    assert repo.inventory == tmp_path / "hosts.yml"


def test_only_the_first_of_several_sources_is_shown(tmp_path: Path) -> None:
    """ansible takes a comma-separated list; pb shows and derives from one."""
    root = _repo(tmp_path, "[defaults]\ninventory = inv/a.yml, inv/b.yml\n")
    assert meta.Repo.discover(root).inventory == root / "inv/a.yml"


def test_a_configured_path_is_honoured_even_when_it_does_not_exist(tmp_path: Path) -> None:
    """A misconfiguration is worth reporting, not silently working around."""
    root = _repo(tmp_path, "[defaults]\ninventory = inventories/typo\n")
    (root / "inventories" / "production").mkdir(parents=True)
    repo = meta.Repo.discover(root)
    assert repo.inventory == root / "inventories/typo"
    assert not repo.inventory.exists()


def test_an_ansible_cfg_pb_cannot_parse_does_not_stop_it(tmp_path: Path) -> None:
    root = _repo(tmp_path, "this is not an ini file\n[[[\n")
    (root / "inventory").mkdir()
    assert meta.Repo.discover(root).inventory_origin == "found"


def test_a_percent_sign_in_ansible_cfg_is_not_interpolated(tmp_path: Path) -> None:
    """ConfigParser would otherwise choke on ansible's own cfg syntax."""
    root = _repo(
        tmp_path,
        "[defaults]\ninventory = inventories/production\n"
        "stdout_callback = yaml\ncallback_whitelist = timer, profile_tasks\n"
        "display_args_to_stdout = False\ncow_selection = random%\n",
    )
    assert meta.Repo.discover(root).inventory == root / "inventories/production"


def test_a_missing_ansible_cfg_is_not_an_error(tmp_path: Path) -> None:
    """find_root gives up and returns the start directory; discover must cope."""
    assert meta.Repo.discover(tmp_path).inventory_origin == "default"


# --- what it derives -------------------------------------------------


def test_group_vars_sits_beside_an_inventory_file(tmp_path: Path) -> None:
    root = _repo(tmp_path, "[defaults]\ninventory = inventories/staging/hosts.yml\n")
    repo = meta.Repo.discover(root)
    assert repo.group_vars_dir == root / "inventories/staging/group_vars"


def test_group_vars_sits_inside_an_inventory_directory(tmp_path: Path) -> None:
    root = _repo(tmp_path, "[defaults]\ninventory = inventories/staging\n")
    (root / "inventories" / "staging").mkdir(parents=True)
    repo = meta.Repo.discover(root)
    assert repo.group_vars_dir == root / "inventories/staging/group_vars"


def test_vaults_are_discovered_beside_a_non_default_inventory(tmp_path: Path) -> None:
    root = _repo(tmp_path, "[defaults]\ninventory = inventories/staging/hosts.yml\n")
    vault = root / "inventories" / "staging" / "group_vars" / "web" / "vault.yml"
    vault.parent.mkdir(parents=True)
    vault.write_text(f"{meta.VAULT_HEADER};1.1;AES256\n3132\n")
    found = meta.discover_vaults(meta.Repo.discover(root))
    assert [(v.group, v.encrypted) for v in found] == [("web", True)]


def test_playbooks_and_roles_do_not_move_with_the_inventory(tmp_path: Path) -> None:
    root = _repo(tmp_path, "[defaults]\ninventory = elsewhere/hosts.yml\n")
    repo = meta.Repo.discover(root)
    assert repo.playbooks_dir == root / "playbooks"
    assert repo.roles_dir == root / "roles"
    assert repo.vault_pass_file == root / ".vault_pass"


# --- the -i pb passes to ansible -------------------------------------


def test_no_dash_i_when_ansible_cfg_already_says_so(tmp_path: Path) -> None:
    """Passing -i would flatten a multi-source setting to its first entry."""
    root = _repo(tmp_path, "[defaults]\ninventory = inv/a.yml, inv/b.yml\n")
    assert meta.Repo.discover(root).inventory_args == []


def test_no_dash_i_when_the_environment_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANSIBLE_INVENTORY", "inventories/staging")
    assert meta.Repo.discover(_repo(tmp_path)).inventory_args == []


def test_dash_i_is_passed_for_an_explicit_flag(tmp_path: Path) -> None:
    root = _repo(tmp_path, "[defaults]\ninventory = inventories/production\n")
    repo = meta.Repo.discover(root, "inventories/dev")
    assert repo.inventory_args == ["-i", "inventories/dev"]


def test_dash_i_is_passed_for_a_path_pb_found_itself(tmp_path: Path) -> None:
    """Without it ansible would fall back to /etc/ansible/hosts."""
    root = _repo(tmp_path)
    (root / "inventory").mkdir()
    assert meta.Repo.discover(root).inventory_args == ["-i", "inventory"]


def test_dash_i_uses_an_absolute_path_when_it_lies_outside_the_repo(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere" / "hosts.yml"
    repo = meta.Repo.discover(_repo(tmp_path / "repo"), str(elsewhere))
    assert repo.inventory_args == ["-i", str(elsewhere)]


def test_rel_shortens_a_path_inside_the_repo(tmp_path: Path) -> None:
    repo = meta.Repo.discover(_repo(tmp_path))
    assert repo.rel(tmp_path / "playbooks" / "site.yml") == "playbooks/site.yml"
    assert repo.rel(Path("/etc/ansible/hosts")) == "/etc/ansible/hosts"


def test_every_origin_discover_can_return_has_a_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Doctor looks the origin up; an unlabelled one would be a blank row."""
    root = _repo(tmp_path)
    seen = {meta.Repo.discover(root).inventory_origin}
    seen.add(meta.Repo.discover(root, "inv").inventory_origin)
    monkeypatch.setenv("ANSIBLE_INVENTORY", "inv")
    seen.add(meta.Repo.discover(root).inventory_origin)
    monkeypatch.delenv("ANSIBLE_INVENTORY")
    (root / "ansible.cfg").write_text("[defaults]\ninventory = inv\n")
    seen.add(meta.Repo.discover(root).inventory_origin)
    (root / "ansible.cfg").write_text("[defaults]\n")
    (root / "inventory").mkdir()
    seen.add(meta.Repo.discover(root).inventory_origin)

    assert seen == {"default", "--inventory", "ANSIBLE_INVENTORY", "ansible.cfg", "found"}
    assert seen <= set(meta.INVENTORY_ORIGINS)


def test_ansible_knows_names_only_real_origins() -> None:
    assert set(meta.ANSIBLE_KNOWS) <= set(meta.INVENTORY_ORIGINS)
