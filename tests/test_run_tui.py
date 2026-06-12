import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import run_tui  # noqa: E402
from run_tui import (  # noqa: E402
    ManagedRun,
    ManagedRunConfig,
    RunTarget,
    active_status_text,
    apply_model_checklist_command,
    build_target_command,
    checkbox,
    checklist_page,
    delete_managed_run_directory,
    delete_target_artifact_files,
    filtered_models,
    filtered_targets,
    model_checklist_candidates,
    parse_checklist_indexes,
    parse_checklist_selection_command,
    powershell_command,
    safe_target_key,
    selected_models_in_order,
    tail_lines,
    update_run_targets,
    write_queue_script,
)


def test_safe_target_key_is_filesystem_friendly() -> None:
    key = safe_target_key("open_source", "openai/gpt-oss-20b:free")

    assert key == "open_source_openai_gpt-oss-20b-free"


def test_build_target_command_for_one_open_source_model(tmp_path) -> None:
    managed = sample_run(tmp_path, [RunTarget("open_source", "openai/gpt-oss-20b:free")])
    command = build_target_command(managed, managed.config.targets[0])

    assert "--resume" in command
    assert "--pause-file" in command
    assert "--skip-deterministic" in command
    assert "--open-source-models" in command
    assert "openai/gpt-oss-20b:free" in command
    assert "--llm-rejection-pause-threshold" in command
    assert str(managed.output_dir) in command


def test_build_target_command_for_deterministic_baseline(tmp_path) -> None:
    managed = sample_run(tmp_path, [RunTarget("scripted")])
    command = build_target_command(managed, managed.config.targets[0])

    assert "--deterministic-episodes" in command
    assert "--skip-llm" in command
    assert "--skip-deterministic" not in command


def test_powershell_command_uses_continuation_lines() -> None:
    text = powershell_command(["python", "eval/run_all_eval.py", "--model", "a/b:c"])

    assert " `\n" in text
    assert "--model" in text
    assert "a/b:c" in text


def test_model_checklist_candidates_put_defaults_first() -> None:
    candidates = model_checklist_candidates(
        ["openai/gpt-oss-20b:free", "qwen/qwen3.6-35b-a3b"],
        ["qwen/qwen3.6-35b-a3b", "google/gemma-4-26b-a4b-it:free"],
    )

    assert candidates == [
        "openai/gpt-oss-20b:free",
        "qwen/qwen3.6-35b-a3b",
        "google/gemma-4-26b-a4b-it:free",
    ]


def test_parse_checklist_indexes_supports_ranges_and_dedupes() -> None:
    indexes = parse_checklist_indexes("1, 3-5, 5, 12, nope, 8-7", max_index=8)

    assert indexes == [1, 3, 4, 5, 7, 8]


def test_parse_checklist_selection_command_supports_select_and_drop() -> None:
    assert parse_checklist_selection_command("select 1-5") == ("select", "1-5")
    assert parse_checklist_selection_command("drop 2,4") == ("drop", "2,4")
    assert parse_checklist_selection_command("1-3") == ("toggle", "1-3")


def test_checkbox_renders_literal_brackets() -> None:
    assert checkbox(True).plain == "[x]"
    assert checkbox(False).plain == "[]"


def test_apply_model_checklist_command_can_force_select_and_drop() -> None:
    candidates = ["a/model", "b/model", "c/model"]
    selected: set[str] = {"a/model"}

    result = apply_model_checklist_command(
        command="select 1-2",
        candidates=candidates,
        visible_page=candidates,
        selected=selected,
        defaults=[],
    )

    assert result.selected == {"a/model", "b/model"}

    result = apply_model_checklist_command(
        command="drop 1",
        candidates=candidates,
        visible_page=candidates,
        selected=result.selected,
        defaults=[],
    )

    assert result.selected == {"b/model"}


def test_checklist_page_clamps_page_and_cursor() -> None:
    values = [str(index) for index in range(40)]

    visible, page, page_count, cursor = checklist_page(values, page=99, cursor=99)

    assert page == 2
    assert page_count == 3
    assert visible == [str(index) for index in range(30, 40)]
    assert cursor == 9


def test_tail_lines_reads_recent_lines(tmp_path) -> None:
    path = tmp_path / "run.log"
    path.write_text("\n".join(f"line {index}" for index in range(10)), encoding="utf-8")

    assert tail_lines(path, 3) == ["line 7", "line 8", "line 9"]


def test_active_status_text_mentions_pause_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_tui, "state_pid_is_running", lambda state: True)

    text = active_status_text({"pid": 123, "target_key": "target"}, pause_requested=True)

    assert "pause requested" in text


def test_selected_models_in_order_preserves_candidate_order_with_extras() -> None:
    selected = selected_models_in_order(
        ["b/model", "a/model"],
        {"z/manual", "a/model"},
    )

    assert selected == ["a/model", "z/manual"]


def test_filtered_models_is_case_insensitive() -> None:
    assert filtered_models(["OpenAI/GPT", "qwen/model"], "openai") == ["OpenAI/GPT"]


def test_filtered_targets_matches_baseline_or_model(tmp_path) -> None:
    managed = sample_run(
        tmp_path,
        [
            RunTarget("random"),
            RunTarget("open_source", "openai/gpt-oss-20b:free"),
        ],
    )

    assert filtered_targets(managed.config.targets, "oss") == [managed.config.targets[1]]
    assert filtered_targets(managed.config.targets, "random") == [managed.config.targets[0]]


def test_update_run_targets_persists_config(tmp_path) -> None:
    managed = sample_run(tmp_path, [RunTarget("random")])
    updated = update_run_targets(
        managed,
        [RunTarget("random"), RunTarget("scripted")],
    )

    assert updated.config_path.exists()
    assert len(updated.config.targets) == 2


def test_write_queue_script_contains_selected_targets(tmp_path) -> None:
    managed = sample_run(
        tmp_path,
        [
            RunTarget("open_source", "openai/gpt-oss-20b:free"),
            RunTarget("scripted"),
        ],
    )
    path = write_queue_script(managed, managed.config.targets)
    text = path.read_text(encoding="utf-8")

    assert "SRE-Zero managed queue" in text
    assert "openai/gpt-oss-20b:free" in text
    assert "--skip-llm" in text


def test_delete_target_artifact_files_removes_result_logs_and_summaries(tmp_path) -> None:
    target = RunTarget("open_source", "openai/gpt-oss-20b:free")
    managed = sample_run(tmp_path, [target])
    artifact_paths = [
        managed.target_output_path(target),
        managed.target_summary_path(target),
        managed.target_log_path(target),
        managed.target_console_log_path(target),
    ]
    for path in artifact_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact", encoding="utf-8")
    command_path = managed.target_command_path(target)
    command_path.parent.mkdir(parents=True, exist_ok=True)
    command_path.write_text("command", encoding="utf-8")

    deleted = delete_target_artifact_files(managed, [target])

    assert deleted == 4
    assert all(not path.exists() for path in artifact_paths)
    assert command_path.exists()


def test_delete_managed_run_directory_removes_child_under_root(tmp_path) -> None:
    managed = sample_run(tmp_path, [RunTarget("random")])
    managed.run_dir.mkdir(parents=True)
    (managed.run_dir / "run.json").write_text("{}", encoding="utf-8")

    delete_managed_run_directory(managed, root=tmp_path)

    assert not managed.run_dir.exists()


def test_delete_managed_run_directory_refuses_unexpected_path(tmp_path) -> None:
    managed = sample_run(tmp_path, [RunTarget("random")])
    managed.run_dir.mkdir(parents=True)

    with pytest.raises(ValueError):
        delete_managed_run_directory(managed, root=tmp_path / "managed")

    assert managed.run_dir.exists()


def sample_run(tmp_path: Path, targets: list[RunTarget]) -> ManagedRun:
    return ManagedRun(
        run_dir=tmp_path / "run",
        config=ManagedRunConfig(
            run_id="test-run",
            created_at="2026-06-11T00:00:00+00:00",
            difficulty="easy",
            seed=0,
            deterministic_episodes=5,
            llm_episodes=1,
            target_steps=8.0,
            timeout_seconds=30.0,
            llm_max_retries=5,
            llm_min_request_interval_seconds=15.0,
            llm_rate_limit_requests=5,
            llm_rate_limit_window_seconds=60.0,
            llm_rejection_pause_threshold=3,
            llm_rejection_pause_seconds=60.0,
            targets=targets,
        ),
    )
