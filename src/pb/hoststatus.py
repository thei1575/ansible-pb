"""A read-only health probe over SSH.

One round trip per host, one compound shell script, no Ansible: this answers
"is the box healthy and is the service up" fast enough to sit behind a tab.
The script is fed on stdin so nothing has to survive shell quoting, and it
only ever reads - nothing here changes a host.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from . import meta

# Emits `key=value` lines. Anything unavailable is simply omitted, so this
# stays portable across whatever a future host happens to run.
PROBE = r"""
exec 2>/dev/null
echo "os=$(. /etc/os-release; echo "${PRETTY_NAME:-unknown}")"
echo "kernel=$(uname -r)"
echo "uptime=$(uptime -p | sed 's/^up //')"
echo "load=$(cut -d' ' -f1-3 /proc/loadavg)"
echo "disk=$(df -h / | awk 'NR==2{print $3"/"$2" ("$5")"}')"
echo "diskpct=$(df -h / | awk 'NR==2{gsub("%","",$5); print $5}')"
echo "mem=$(free -h | awk '/^Mem:/{print $3"/"$2}')"
if [ -f /var/run/reboot-required ]; then echo "reboot=yes"; else echo "reboot=no"; fi
echo "updates=$(apt-get -s -o Debug::NoLocking=true upgrade | grep -c '^Inst')"
failed=$(systemctl list-units --state=failed --no-legend --plain \
  | awk '{print $1}' | paste -sd, -)
echo "failed=$failed"
echo "services=$(systemctl list-units --type=service --state=running --no-legend --plain | wc -l)"
docker ps --format '{{.Names}}\t{{.Status}}' | while IFS= read -r line; do
  echo "docker=$line"
done
for host in __FQDNS__; do
  cert="/etc/letsencrypt/live/$host/cert.pem"
  if [ -f "$cert" ]; then
    echo "cert=$host	$(openssl x509 -enddate -noout -in "$cert" | cut -d= -f2)"
  fi
done
"""


@dataclass
class HostStatus:
    host: str
    reachable: bool = False
    local: bool = False
    error: str = ""
    values: dict[str, str] = field(default_factory=dict)
    containers: list[tuple[str, str]] = field(default_factory=list)
    certs: list[tuple[str, str]] = field(default_factory=list)

    def get(self, key: str, default: str = "-") -> str:
        return self.values.get(key) or default

    @property
    def failed_units(self) -> list[str]:
        raw = self.values.get("failed", "")
        return [u for u in raw.split(",") if u]

    @property
    def disk_pct(self) -> int:
        try:
            return int(self.values.get("diskpct", "0"))
        except ValueError:
            return 0

    @property
    def healthy(self) -> bool:
        return self.reachable and not self.failed_units and self.disk_pct < 90


def probe(host: meta.Host, timeout: int = 45) -> HostStatus:
    """Run the probe against one host. Returns a status either way."""
    status = HostStatus(host=host.name)

    if host.vars.get("ansible_connection") == "local" or host.name == "localhost":
        status.local = True
        status.error = "local connection - nothing to probe"
        return status

    target = host.address or host.name
    user = str(host.vars.get("ansible_user", "root"))
    fqdns = sorted(
        str(v) for k, v in host.vars.items()
        if k.endswith("_fqdn") and isinstance(v, str) and v
    )
    script = PROBE.replace("__FQDNS__", " ".join(fqdns) or "''")

    try:
        proc = subprocess.run(
            [
                "ssh",
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=8",
                "-o", "StrictHostKeyChecking=accept-new",
                f"{user}@{target}",
                "bash -s",
            ],
            input=script.encode(),
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        status.error = "ssh not found on PATH"
        return status
    except subprocess.TimeoutExpired:
        status.error = f"no answer within {timeout}s"
        return status

    if proc.returncode != 0 and not proc.stdout:
        status.error = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:][0] \
            if proc.stderr.strip() else f"ssh exited {proc.returncode}"
        return status

    status.reachable = True
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        key, _, value = line.partition("=")
        value = value.strip()
        if key == "docker" and value:
            name, _, state = value.partition("\t")
            status.containers.append((name, state))
        elif key == "cert" and value:
            name, _, expiry = value.partition("\t")
            status.certs.append((name, expiry))
        elif key:
            status.values[key] = value
    return status
