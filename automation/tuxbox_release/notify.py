"""Mail, GitHub issues and the dead man's switch."""
from __future__ import annotations

import hashlib
import os
import socket
import subprocess
from datetime import date

from .config import Config

#: Day of month after which a missing run counts as a failure.
GRACE_DAYS = 5


def mail_subject(what: str) -> str:
    """Prefix a subject with the host this runs on.

    Which host that is belongs to the installation, not to the source: a
    name baked in here would be wrong everywhere else - and would put a
    private machine name into a public repository.
    """
    return f"{socket.gethostname()}: {what}"


def send_mail(cfg: Config, subject: str, body: str) -> None:
    """Plain mail through the host's msmtp setup."""
    if not cfg.mail_to:
        return
    message = f"To: {cfg.mail_to}\nSubject: {subject}\n\n{body}\n"
    subprocess.run(["msmtp", cfg.mail_to], input=message, text=True, check=False)


def issue_fingerprint(machine: str, reason: str) -> str:
    """Stable short hash so a recurring failure reuses its issue."""
    digest = hashlib.sha256(f"{machine}|{reason}".encode("utf-8")).hexdigest()
    return digest[:12]


def open_issue(cfg: Config, title: str, body: str, fingerprint: str) -> None:
    """Open an issue, or comment on the existing one for this fingerprint."""
    env = dict(os.environ, GH_TOKEN=cfg.token)
    search = subprocess.run(
        ["gh", "issue", "list", "--repo", cfg.repo, "--state", "open",
         "--search", fingerprint, "--json", "number", "--jq", ".[0].number"],
        capture_output=True, text=True, env=env, check=False)
    existing = search.stdout.strip()
    full_body = f"{body}\n\n<!-- fingerprint: {fingerprint} -->"
    if existing:
        subprocess.run(["gh", "issue", "comment", existing, "--repo", cfg.repo,
                        "--body", full_body], env=env, check=False)
    else:
        subprocess.run(["gh", "issue", "create", "--repo", cfg.repo,
                        "--title", title, "--body", full_body],
                       env=env, check=False)


def deadman_message(state: dict | None, today: date) -> str | None:
    """Alarm text when this month has no successful run yet.

    This covers the one failure mode nothing else can see: the host never
    woke up, so no build ran, no log exists and nothing reached GitHub.
    """
    if today.day <= GRACE_DAYS:
        return None
    month = f"{today.year}-{today.month:02d}"
    if state is None:
        return (f"Es liegt kein einziger Buildlauf vor. Erwartet war einer "
                f"im Monat {month}.")
    build_id = state.get("build_id", "")
    ran_this_month = build_id[:6] == f"{today.year}{today.month:02d}"
    succeeded = any(p.get("phase") == "finish" and p.get("status") == "ok"
                    for p in state.get("phases", []))
    if ran_this_month and succeeded:
        return None
    if not ran_this_month:
        return (f"Im Monat {month} hat kein Build stattgefunden. Letzter Lauf: "
                f"{build_id or 'unbekannt'}. Vermutlich ist der Host nicht "
                f"aufgewacht - Weckalarm und Timer pruefen.")
    return (f"Der Buildlauf {build_id} im Monat {month} war nicht erfolgreich. "
            f"Log und Statusdatei pruefen.")
