import json
import pytest
from tuxbox_release.state import BuildState, new_build_id, acquire_lock, last_state


def test_build_id_is_sortable_utc():
    build_id = new_build_id()
    assert len(build_id) == 16 and build_id.endswith("Z") and "T" in build_id


def test_phase_transitions_are_recorded(tmp_path):
    state = BuildState(tmp_path, "20260922T060000Z")
    state.start("build")
    state.finish("build", "ok", machines=3)
    data = state.read()
    assert data["phases"][-1]["phase"] == "build"
    assert data["phases"][-1]["status"] == "ok"
    assert data["phases"][-1]["machines"] == 3
    assert data["phases"][-1]["ended"] is not None


def test_machine_results_accumulate(tmp_path):
    state = BuildState(tmp_path, "20260922T060000Z")
    state.machine_result("hd51", "ok", image_version="4.0.35.486")
    state.machine_result("hd60", "failed", reason="do_compile")
    data = state.read()
    assert data["machines"]["hd51"]["status"] == "ok"
    assert data["machines"]["hd60"]["reason"] == "do_compile"


def test_last_state_points_at_newest_run(tmp_path):
    BuildState(tmp_path, "20260901T060000Z").finish("finish", "ok")
    BuildState(tmp_path, "20261001T060000Z").finish("finish", "ok")
    assert last_state(tmp_path)["build_id"] == "20261001T060000Z"


def test_lock_refuses_second_holder(tmp_path):
    with acquire_lock(tmp_path):
        with pytest.raises(RuntimeError, match="läuft bereits"):
            with acquire_lock(tmp_path):
                pass


def test_lock_is_released_after_exception(tmp_path):
    with pytest.raises(ZeroDivisionError):
        with acquire_lock(tmp_path):
            1 / 0
    with acquire_lock(tmp_path):
        pass
