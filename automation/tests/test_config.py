import os
import pytest
from pathlib import Path
from tuxbox_release.config import load_config, Machine


def write_env(tmp_path: Path, **overrides) -> Path:
    values = {
        "TUXBOX_WORK_ROOT": "/mnt/C/tuxbox-build",
        "TUXBOX_TMP_ROOT": "/mnt/build",
        "TUXBOX_ARCHIVE_ROOT": "/mnt/archiv/releases",
        "TUXBOX_IMAGE": "tuxbox-build:ci",
        "TUXBOX_MACHINES": "hd51:mutant51,hd60:ax60,h7:zgemmah7",
        "TUXBOX_REPO": "tuxbox-neutrino/build-environment",
        "TUXBOX_CHANNEL": "release",
        "TUXBOX_MAIL_TO": "ops@example.org",
        "GH_TOKEN": "secret",
    }
    values.update(overrides)
    path = tmp_path / "env"
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
    path.chmod(0o600)
    return path


def test_parses_machine_table(tmp_path):
    cfg = load_config(write_env(tmp_path))
    assert cfg.machines == (
        Machine("hd51", "mutant51"),
        Machine("hd60", "ax60"),
        Machine("h7", "zgemmah7"),
    )


def test_machinebuild_defaults_to_machine(tmp_path):
    cfg = load_config(write_env(tmp_path, TUXBOX_MACHINES="hd51"))
    assert cfg.machines == (Machine("hd51", "hd51"),)


def test_rejects_world_readable_env(tmp_path):
    path = write_env(tmp_path)
    path.chmod(0o644)
    with pytest.raises(PermissionError, match="0644"):
        load_config(path)


def test_rejects_placeholder_token(tmp_path):
    with pytest.raises(ValueError, match="GH_TOKEN"):
        load_config(write_env(tmp_path, GH_TOKEN="CHANGEME"))


def test_dry_run_may_start_without_a_real_token(tmp_path):
    # A dry run builds nothing and uploads nothing, so it must not be
    # blocked before the bot account exists.
    cfg = load_config(write_env(tmp_path, GH_TOKEN="CHANGEME"), require_secrets=False)
    assert cfg.token == "CHANGEME"


def test_checkout_is_derived_from_work_root(tmp_path):
    cfg = load_config(write_env(tmp_path))
    assert cfg.checkout == Path("/mnt/C/tuxbox-build/build-environment")


# --- mirrors belong in the environment file, not in the source ------------

def test_mirrors_are_read_from_the_environment(tmp_path):
    # Their paths name the host they come from, which has no business in a
    # public repository - and they differ per installation anyway.
    cfg = load_config(write_env(
        tmp_path, TUXBOX_MIRRORS="/mnt/sstate-mirror,/mnt/downloads-mirror"))
    assert cfg.mirrors == ("/mnt/sstate-mirror", "/mnt/downloads-mirror")


def test_no_mirrors_configured_is_fine(tmp_path):
    # An installation without a second host is the normal case; it just
    # builds without the extra cache.
    assert load_config(write_env(tmp_path)).mirrors == ()


def test_blank_entries_in_the_mirror_list_are_dropped(tmp_path):
    cfg = load_config(write_env(tmp_path, TUXBOX_MIRRORS="/mnt/a, ,/mnt/b,"))
    assert cfg.mirrors == ("/mnt/a", "/mnt/b")
