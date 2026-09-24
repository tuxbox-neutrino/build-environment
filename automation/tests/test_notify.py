from datetime import date
from tuxbox_release.notify import (deadman_message, issue_fingerprint,
                                   mail_subject)


def state(build_id, status="ok"):
    return {"build_id": build_id, "phases": [{"phase": "finish", "status": status}]}


def test_silent_when_this_month_succeeded():
    assert deadman_message(state("20261001T060000Z"), date(2026, 10, 15)) is None


def test_alarms_when_no_run_happened_this_month():
    msg = deadman_message(state("20260901T060000Z"), date(2026, 10, 15))
    assert msg is not None and "2026-10" in msg


def test_alarms_when_nothing_ever_ran():
    assert deadman_message(None, date(2026, 10, 15)) is not None


def test_stays_silent_during_the_grace_period():
    assert deadman_message(state("20260901T060000Z"), date(2026, 10, 2)) is None


def test_alarms_when_this_months_run_failed():
    msg = deadman_message(state("20261001T060000Z", status="failed"), date(2026, 10, 15))
    assert msg is not None


def test_missing_wakeup_is_named_as_the_likely_cause():
    msg = deadman_message(state("20260901T060000Z"), date(2026, 10, 15))
    assert "aufgewacht" in msg


def test_fingerprint_is_stable_for_the_same_failure():
    a = issue_fingerprint("hd51", "do_compile failed in linux-tuxbox")
    b = issue_fingerprint("hd51", "do_compile failed in linux-tuxbox")
    assert a == b and len(a) == 12


def test_fingerprint_differs_per_machine():
    assert issue_fingerprint("hd51", "x") != issue_fingerprint("hd60", "x")


def test_the_mail_subject_names_the_host_at_runtime(monkeypatch):
    # It used to be hard-coded, which put the machine's name into a public
    # repository and made the code wrong on any other host.
    monkeypatch.setattr("tuxbox_release.notify.socket.gethostname",
                        lambda: "somehost")
    assert mail_subject("Monatsbuild fehlt") == "somehost: Monatsbuild fehlt"
