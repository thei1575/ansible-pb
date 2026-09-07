"""The read-only SSH health probe."""

from __future__ import annotations

from pb import hoststatus, meta


def _status(**values: str) -> hoststatus.HostStatus:
    return hoststatus.HostStatus(host="web01", reachable=True, values=dict(values))


def test_get_falls_back_to_a_dash() -> None:
    status = _status(uptime="3 days", mem="")
    assert status.get("uptime") == "3 days"
    assert status.get("mem") == "-"
    assert status.get("missing") == "-"
    assert status.get("missing", default="n/a") == "n/a"


def test_failed_units_splits_the_comma_list() -> None:
    assert _status(failed="nginx.service,cron.service").failed_units == [
        "nginx.service",
        "cron.service",
    ]
    assert _status(failed="").failed_units == []
    assert _status().failed_units == []


def test_disk_pct_is_zero_when_the_probe_said_nothing_usable() -> None:
    assert _status(diskpct="87").disk_pct == 87
    assert _status(diskpct="").disk_pct == 0
    assert _status(diskpct="n/a").disk_pct == 0
    assert _status().disk_pct == 0


def test_healthy_needs_reachable_no_failed_units_and_disk_room() -> None:
    assert _status(diskpct="40").healthy
    assert not _status(diskpct="95").healthy
    assert not _status(diskpct="40", failed="nginx.service").healthy
    assert not hoststatus.HostStatus(host="web01", reachable=False).healthy


def test_disk_at_the_threshold_is_still_unhealthy() -> None:
    assert _status(diskpct="89").healthy
    assert not _status(diskpct="90").healthy


def test_probe_does_not_ssh_to_a_local_connection() -> None:
    """A local host has nothing to probe, and must not be reached over ssh."""
    host = meta.Host(
        name="control", address="", groups=["all"], vars={"ansible_connection": "local"}
    )
    status = hoststatus.probe(host)
    assert status.local
    assert not status.reachable
    assert "local" in status.error


def test_probe_skips_localhost_by_name() -> None:
    host = meta.Host(name="localhost", address="127.0.0.1", groups=["all"], vars={})
    assert hoststatus.probe(host).local


def test_the_probe_script_only_reads() -> None:
    """The Status tab must never change a host. Guard the script itself."""
    for verb in ("rm ", "systemctl start", "systemctl stop", "systemctl restart",
                 "apt-get install", "apt-get upgrade\n", "docker run", "docker rm",
                 "> /etc", "reboot\n", "chmod ", "chown "):
        assert verb not in hoststatus.PROBE, f"probe script contains {verb!r}"


def test_the_probe_asks_apt_to_simulate_rather_than_install() -> None:
    assert "apt-get -s" in hoststatus.PROBE
