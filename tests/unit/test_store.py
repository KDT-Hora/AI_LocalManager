import pytest

from ai_orchestrator.models.artifact import ArtifactKind
from ai_orchestrator.store import files
from ai_orchestrator.store.task_store import TaskStore


def new_task(store):
    return store.create_task("req", ["story"], 3, "the prompt")


def test_atomic_write_no_leftover_tmp(tmp_path):
    p = tmp_path / "a.json"
    files.atomic_write_text(p, "日本語")
    assert p.read_text(encoding="utf-8") == "日本語"
    assert not list(tmp_path.glob("*.tmp"))
    assert not p.read_bytes().startswith(b"\xef\xbb\xbf")  # no BOM


def test_write_new_refuses_overwrite(tmp_path):
    p = tmp_path / "x.txt"
    files.write_new_text(p, "1")
    with pytest.raises(FileExistsError):
        files.write_new_text(p, "2")


def test_task_ids_sequential(tmp_path):
    store = TaskStore(tmp_path)
    assert new_task(store).task_id == "TASK-001"
    assert new_task(store).task_id == "TASK-002"


def test_versions_sequential_and_preserved(tmp_path):
    store = TaskStore(tmp_path)
    t = new_task(store)
    v1 = store.save_version(t, "one", "txt", ArtifactKind.INITIAL, "m", "the prompt")
    v2 = store.save_version(t, "two", "txt", ArtifactKind.MINOR_REVISION, "m", "p2", 1)
    assert (v1.version, v2.version) == (1, 2)
    assert v1.prompt_file == "prompt.txt" and v2.prompt_file == "prompt_v002.txt"
    assert store.read_version(t.task_id, 1)[1] == "one"
    assert t.versions == [1, 2]


def test_user_edit_imported_and_original_kept(tmp_path):
    store = TaskStore(tmp_path)
    t = new_task(store)
    store.save_version(t, "ai text", "txt", ArtifactKind.INITIAL, "m", "the prompt")
    store.save(t)
    (store.task_dir(t.task_id) / "result_v001.txt").write_text("edited by user", encoding="utf-8")
    created = store.sync_user_edits(t)
    assert len(created) == 1 and created[0].kind == ArtifactKind.USER_EDIT
    assert created[0].version == 2 and created[0].parent_version == 1
    assert store.read_version(t.task_id, 2)[1] == "edited by user"
    assert store.read_version(t.task_id, 1)[1] == "ai text"  # AI version restored
    assert store.sync_user_edits(t) == []  # idempotent


def test_corrupted_task_json_reported_not_modified(tmp_path):
    store = TaskStore(tmp_path)
    t = new_task(store)
    path = store.task_dir(t.task_id) / "task.json"
    path.write_text("{ broken", encoding="utf-8")
    from ai_orchestrator.errors import OrchestratorError

    with pytest.raises(OrchestratorError) as e:
        store.load(t.task_id)
    assert e.value.kind == "corrupted_data"
    assert path.read_text(encoding="utf-8") == "{ broken"
