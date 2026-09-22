from pathlib import Path
from tuxbox_release.runner import preflight, PHASES, MIN_FREE_GB
from tuxbox_release.config import Config, Machine


def make_config(tmp_path: Path) -> Config:
    return Config(
        work_root=tmp_path / "work", tmp_root=tmp_path / "ssd",
        archive_root=tmp_path / "archive", image="tuxbox-build:ci",
        machines=(Machine("hd51", "mutant51"),),
        repo="tuxbox-neutrino/build-environment", channel="release",
        mail_to="ops@example.org", token="secret",
    )


def test_phases_are_in_the_documented_order():
    # No separate "verify": deploy-info --require-images --require-manifest
    # and select_assets already refuse an incomplete build.
    assert PHASES == ("preflight", "update", "build", "collect", "publish", "finish")


def test_preflight_complains_about_missing_work_root(tmp_path):
    assert any("work_root" in p for p in preflight(make_config(tmp_path)))


def test_preflight_complains_about_a_missing_checkout(tmp_path):
    cfg = make_config(tmp_path)
    cfg.work_root.mkdir(parents=True)
    cfg.tmp_root.mkdir(parents=True)
    cfg.archive_root.mkdir(parents=True)
    assert any("build-environment" in p for p in preflight(cfg))


def test_preflight_is_silent_when_everything_is_in_place(tmp_path, monkeypatch):
    # Free space is patched: the test dirs live under /tmp, which is a
    # 16 GB tmpfs here and would trip the threshold for reasons that have
    # nothing to do with what this test checks.
    monkeypatch.setattr("tuxbox_release.runner.free_gb", lambda path: 500)
    cfg = make_config(tmp_path)
    (cfg.checkout / ".git").mkdir(parents=True)
    cfg.tmp_root.mkdir(parents=True)
    cfg.archive_root.mkdir(parents=True)
    assert preflight(cfg) == []


def test_preflight_refuses_to_start_without_space(tmp_path, monkeypatch):
    monkeypatch.setattr("tuxbox_release.runner.free_gb", lambda path: MIN_FREE_GB - 1)
    cfg = make_config(tmp_path)
    (cfg.checkout / ".git").mkdir(parents=True)
    cfg.tmp_root.mkdir(parents=True)
    cfg.archive_root.mkdir(parents=True)
    problems = preflight(cfg)
    assert problems and all("zu wenig Platz" in p for p in problems)


def test_free_space_threshold_is_stated_not_implied():
    assert MIN_FREE_GB >= 60
