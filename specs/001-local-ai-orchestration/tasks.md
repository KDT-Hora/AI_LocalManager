---

description: "Task list for ローカルAIサブエージェント統括システム"
---

# Tasks: ローカルAIサブエージェント統括システム

**Input**: Design documents from `/specs/001-local-ai-orchestration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: plan.md の Testing 方針（pytest + フェイクLM Studio）に従い、契約・結合・単体テストを含める。各ストーリーでテストを先に書き、失敗を確認してから実装する。

**Organization**: ユーザーストーリー単位でグループ化し、各ストーリーを独立して実装・検証できる。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並列実行可（別ファイル、未完了タスクへの依存なし）
- **[Story]**: 対応するユーザーストーリー（US1〜US4）
- パスはすべてリポジトリルートからの相対パス

## Path Conventions

単一プロジェクト: `src/ai_orchestrator/`, `tests/`, `config/`, `workspace/`（plan.md の Project Structure に従う）

---

## Phase 1: Setup

**Purpose**: プロジェクト初期化

- [X] T001 Create project structure per plan.md: `src/ai_orchestrator/{models,registry,backends,store,workflow}/` with `__init__.py`, `tests/{contract,integration,unit}/`, `config/`, `workspace/`
- [X] T002 Create `pyproject.toml` (Python >=3.11) with dependencies: mcp, httpx, pydantic>=2, PyYAML, filelock; dev: pytest, pytest-asyncio, respx, ruff
- [X] T003 [P] Configure ruff and pytest (asyncio_mode=auto) in `pyproject.toml`
- [X] T004 [P] Add `.gitignore` entries for `workspace/`, `__pycache__/`, `.venv/`
- [X] T005 [P] Create sample `config/models.yaml` with one text model following `specs/001-local-ai-orchestration/contracts/model-definition.schema.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全ストーリーが依存する基盤

**⚠️ CRITICAL**: このフェーズ完了までユーザーストーリーの作業は開始できない

- [X] T006 Verify the installed LM Studio version's API: confirm `/v1/models`, `/v1/chat/completions`, and how model load/unload works (JIT load, `lms` CLI, or management REST). Record findings as a comment block at the top of `src/ai_orchestrator/backends/lmstudio.py` and update research.md R3 (Decision) accordingly
- [X] T007 [P] Define error types in `src/ai_orchestrator/errors.py` with kinds: `no_capable_model`, `model_load_failed`, `backend_unreachable`, `timeout`, `invalid_output`, `invalid_transition`, `revision_limit_reached`, `not_found`, `unsupported_backend`; each carries `message` and `retryable`
- [X] T008 [P] Implement `ModelDefinition` in `src/ai_orchestrator/models/model_definition.py` per data-model.md: `id` unique, `capabilities` non-empty (1件以上), `priority` int 0–100, `max_context` > 0, `required_vram_gb` ≥ 0, `output_format` enum text/json/code/image, `model_type` enum llm/vision/image_gen, `enabled` bool default true
- [X] T009 [P] Implement `Task` and `TaskState` enum (PENDING, RUNNING, REVIEWING, REVISION_REQUIRED, RETRYING, COMPLETED, FAILED) in `src/ai_orchestrator/models/task.py`: `task_id` format `TASK-` + 3桁以上の連番, `state_history` append-only, `revision_count` ≤ `max_revisions` (default 3), `error` {kind, message, retryable}
- [X] T010 [P] Implement `ArtifactVersion` (kind enum: initial/minor_revision/regenerate/model_switch/user_edit; `version` starts at 1, no gaps) in `src/ai_orchestrator/models/artifact.py`
- [X] T011 [P] Implement `ValidationResult` (verdict pass/fail; `issues` required when verdict=fail; `recommended_action` enum minor/regenerate/switch_model) and `RevisionRequest` (method enum minor/regenerate/switch_model) in `src/ai_orchestrator/models/validation.py`
- [X] T012 Implement file store primitives in `src/ai_orchestrator/store/files.py`: atomic write (temp file → rename), UTF-8 without BOM, per-task file lock (filelock), append-only version numbering that refuses to overwrite existing `result_vNNN` files
- [X] T013 Implement task store in `src/ai_orchestrator/store/task_store.py`: create task dir `workspace/tasks/TASK-NNN/`, load/save `task.json`, allocate next task_id, read-only reporting for corrupted JSON per contracts/task-files.md rule 5 (depends on T009, T012)
- [X] T014 Implement state machine in `src/ai_orchestrator/workflow/state_machine.py` with the transition table from data-model.md; reject invalid transitions with `invalid_transition`; append every transition to `state_history` (depends on T007, T009)
- [X] T015 [P] Implement settings loader in `src/ai_orchestrator/settings.py`: workspace path, models.yaml path, LM Studio base URL (default `http://localhost:1234`), generation timeout (default 300s), default `max_revisions` (3), `vram_limit_gb`
- [X] T016 [P] Implement fake LM Studio server for tests in `tests/fakes/fake_lmstudio.py`: OpenAI-compatible `/v1/models` and `/v1/chat/completions`, with switches to simulate unreachable, load failure, timeout, and malformed output
- [X] T017 [P] Unit tests for state machine transitions (valid, invalid, history append) in `tests/unit/test_state_machine.py`
- [X] T018 [P] Unit tests for file store (atomic write, no-overwrite, sequential versions, lock) in `tests/unit/test_store.py`

**Checkpoint**: 基盤完了。ユーザーストーリーに着手可能

---

## Phase 3: User Story 1 - タスクを依頼して成果物を得る (Priority: P1) 🎯 MVP

**Goal**: 依頼 → 能力に基づくモデル選択 → 生成 → 成果物保存 → Claudeが取得

**Independent Test**: 1モデル登録、テキスト生成タスクを1件実行し、`result_v001.*` と `task.json`（使用モデル・プロンプト・日時）が保存され、`get_artifact` で内容を取得できる。能力なし依頼は `no_capable_model`、未ロードモデルは自動ロードされる

### Tests for User Story 1 ⚠️ 先に書いて失敗を確認

- [X] T019 [P] [US1] Contract tests for `create_task`, `select_model`, `run_agent`, `get_artifact` input/output shapes in `tests/contract/test_mcp_tools_us1.py` (per contracts/mcp-tools.md)
- [X] T020 [P] [US1] Integration test: request → select → run → artifact saved, using fake LM Studio, in `tests/integration/test_us1_generate.py`
- [X] T021 [P] [US1] Integration test: no capable model → `no_capable_model` and task FAILED, in `tests/integration/test_us1_no_model.py`
- [X] T022 [P] [US1] Integration tests for failures (`backend_unreachable`, `model_load_failed`, `timeout`, `invalid_output`): task never left in RUNNING, in `tests/integration/test_us1_failures.py`
- [X] T023 [P] [US1] Unit tests for model selection (capability match, priority order, loaded-model tie-break) in `tests/unit/test_selection_basic.py`

### Implementation for User Story 1

- [X] T024 [P] [US1] Implement model registry loader (parse and validate `config/models.yaml` with `ModelDefinition`, reject duplicate `id`) in `src/ai_orchestrator/registry/loader.py`
- [X] T025 [US1] Implement model selection in `src/ai_orchestrator/registry/selection.py`: enabled only → all required capabilities → priority descending; ties prefer currently loaded model; return reason and candidate list with `rejected_reason` (depends on T024)
- [X] T026 [P] [US1] Implement LM Studio client in `src/ai_orchestrator/backends/lmstudio.py`: list models, ensure model loaded (method decided in T006), chat completion with timeout; unload the previously loaded model when switching models if `vram_limit_gb` would be exceeded (FR-004); map failures to typed errors (depends on T006, T007, T015, T027)
- [X] T027 [P] [US1] Implement backend interface `src/ai_orchestrator/backends/base.py`; for `model_type=image_gen` raise `unsupported_backend` (research R4)
- [X] T028 [US1] Implement generation workflow in `src/ai_orchestrator/workflow/runner.py`: PENDING → RUNNING, load model, send prompt, save `result_v001.<ext>` + `result_v001.meta.json`, record model_id/prompt/timestamps, RUNNING → REVIEWING; on any error set FAILED with `error` recorded (depends on T013, T014, T025, T026)
- [X] T029 [US1] Implement MCP server skeleton and tools `create_task`, `select_model`, `run_agent`, `get_artifact` in `src/ai_orchestrator/mcp_server.py` (stdio, JSON responses `{ok, ...}` / `{ok:false, error}`) (depends on T028)
- [X] T030 [US1] Add structured logging for task lifecycle events in `src/ai_orchestrator/logging_setup.py` and wire into runner and MCP server

**Checkpoint**: US1 単体で動作・検証可能（MVP）。quickstart シナリオ 1, 2, 8 を確認

---

## Phase 4: User Story 2 - 成果物の検証と修正ループ (Priority: P2)

**Goal**: Claudeの検証結果を登録し、軽微修正・再生成・AI変更で修正版を作り、合格したら完了する

**Independent Test**: 必須項目が欠けた成果物を fail 登録 → 修正指示 → v002 保存（v001 保持）→ pass 登録 → 完了。上限超過で FAILED

### Tests for User Story 2 ⚠️

- [X] T031 [P] [US2] Contract tests for `validate_artifact`, `request_revision`, `complete_task` in `tests/contract/test_mcp_tools_us2.py`
- [X] T032 [P] [US2] Integration test: fail → minor revision → v002 → pass → COMPLETED (v001 retained), in `tests/integration/test_us2_minor.py`
- [X] T033 [P] [US2] Integration test: regenerate and switch_model (different `model_id` recorded on new version), in `tests/integration/test_us2_regen_switch.py`
- [X] T034 [P] [US2] Integration test: revision limit reached → `revision_limit_reached`, FAILED, in `tests/integration/test_us2_limit.py`
- [X] T035 [P] [US2] Integration test: `complete_task` without a passing validation is rejected with `invalid_transition`, in `tests/integration/test_us2_no_unvalidated_complete.py`

### Implementation for User Story 2

- [X] T036 [P] [US2] Implement validation store in `src/ai_orchestrator/store/validation_store.py`: save `validation_vNNN.json` linked to its version; `issues` required for fail
- [X] T037 [US2] Implement `validate_artifact` logic in `src/ai_orchestrator/workflow/validation.py`: pass keeps REVIEWING (complete allowed); fail → REVISION_REQUIRED (depends on T014, T036)
- [X] T038 [US2] Implement revision workflow in `src/ai_orchestrator/workflow/revision.py`: `minor` (existing version + instructions, same model), `regenerate` (from scratch, same model), `switch_model` (select excluding `excluded_model_ids`, or `target_model_id`); write `prompt_vNNN.txt`, increment `revision_count`, fail with `revision_limit_reached` when over `max_revisions`; REVISION_REQUIRED → RETRYING → RUNNING → REVIEWING (depends on T028, T037)
- [X] T039 [US2] Implement `complete_task` in `src/ai_orchestrator/workflow/completion.py`: require a `pass` validation on the given version (FR-020), set `final_version`, copy final result to `workspace/artifacts/<category>/<name>_<task_id>.<ext>` where `<category>` = `Task.category` (first required capability) (depends on T037)
- [X] T040 [US2] Register `validate_artifact`, `request_revision`, `complete_task` tools in `src/ai_orchestrator/mcp_server.py` (depends on T038, T039)

**Checkpoint**: US1 + US2 が独立に動作。quickstart シナリオ 3, 4, 5, 6 を確認

---

## Phase 5: User Story 3 - モデルの登録・変更 (Priority: P3)

**Goal**: 再ビルドなしでモデル定義を追加・変更・無効化でき、制約（コンテキスト・VRAM）を考慮して選択される

**Independent Test**: モデルを追加すると該当能力のタスクで選ばれ、`enabled: false` にすると選ばれない。進行中タスクは影響を受けない

### Tests for User Story 3 ⚠️

- [X] T041 [P] [US3] Unit tests for constraint filtering (`max_context` vs estimated input, `required_vram_gb` vs `vram_limit_gb`) and rejected reasons, in `tests/unit/test_selection_constraints.py`
- [X] T042 [P] [US3] Integration test: edit `models.yaml` between tasks (priority change, `enabled: false`, new model) takes effect on next task without restart; in-flight task unchanged, in `tests/integration/test_us3_reload.py`
- [X] T043 [P] [US3] Unit tests for `models.yaml` validation errors (duplicate id, empty capabilities, out-of-range priority), in `tests/unit/test_registry_validation.py`

### Implementation for User Story 3

- [X] T044 [US3] Extend selection in `src/ai_orchestrator/registry/selection.py`: reject models whose `max_context` is below the estimated input tokens (estimate = ceil(chars / 2) + `max_tokens`, per research.md R6) or whose `required_vram_gb` exceeds `vram_limit_gb`, recording `rejected_reason` (depends on T025)
- [X] T045 [US3] Reload `config/models.yaml` at each task start (mtime check) in `src/ai_orchestrator/registry/loader.py`; freeze the selected model definition into `task.json` field `model_snapshot` so in-flight tasks are unaffected
- [X] T046 [US3] Implement CLI `check-models` command (validate `models.yaml`, print errors with field names) in `src/ai_orchestrator/cli.py`
- [X] T047 [P] [US3] Extend `config/models.yaml` (from T005) with commented examples for Qwen/Mistral/Gemma/code models (examples only)

**Checkpoint**: US1〜US3 が独立に動作。quickstart シナリオ 7 を確認

---

## Phase 6: User Story 4 - 状態と履歴の把握、ユーザーによる最終確認・編集 (Priority: P3)

**Goal**: タスク一覧・履歴を確認でき、成果物を手編集しても履歴が保たれる。中断後も復旧できる

**Independent Test**: 完了済みタスクの状態・版履歴・検証結果を閲覧、成果物を手編集すると `user_edit` の新版として取り込まれ AI 生成版も残る。強制終了後に RUNNING タスクが FAILED(retryable) になる

### Tests for User Story 4 ⚠️

- [X] T048 [P] [US4] Integration test: manual edit of `result_vNNN` is detected and imported as `user_edit` while the AI version stays, in `tests/integration/test_us4_user_edit.py`
- [X] T049 [P] [US4] Integration test: stale RUNNING task at startup becomes FAILED with `retryable=true`, saved versions intact, in `tests/integration/test_us4_recovery.py`
- [X] T050 [P] [US4] Unit tests for CLI list/show output (state, model, revision count, validation per version), in `tests/unit/test_cli_views.py`

### Implementation for User Story 4

- [X] T051 [US4] Implement CLI `list` and `show <task_id>` in `src/ai_orchestrator/cli.py` (state, history, models used, revision count, per-version validation); highlight FAILED tasks with their `error.message` so the user is notified of failures (FR-010) (depends on T013, T036)
- [X] T052 [US4] Implement user-edit detection (compare file SHA-256 with `content_hash` in `result_vNNN.meta.json`) that creates a `user_edit` version with `parent_version` in `src/ai_orchestrator/store/user_edit.py`; call it on task load per contracts/task-files.md rule 3 (depends on T012)
- [X] T053 [US4] Implement startup recovery in `src/ai_orchestrator/workflow/recovery.py`: move stale RUNNING/RETRYING tasks to FAILED with `retryable=true` and a recorded reason; invoke at MCP server start (depends on T013, T014)
- [X] T054 [US4] Implement CLI `retry <task_id>` (FAILED retryable → PENDING) in `src/ai_orchestrator/cli.py` (depends on T014)

**Checkpoint**: 全ストーリーが独立に動作。quickstart シナリオ 9, 10 を確認

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T055 [P] Write `README.md`: setup, registering the MCP server with Claude (stdio command), `models.yaml` guide, section "Capabilities" listing the recommended capability vocabulary (story, character_design, worldbuilding, analysis, code, review), note that image generation is not supported in v1 (research R4)
- [X] T056 [P] Add MCP registration example (`.mcp.json` snippet) in `docs/mcp-setup.md`
- [X] T057 Run all scenarios in `specs/001-local-ai-orchestration/quickstart.md` against a real LM Studio model and record the results at the bottom of quickstart.md (done: real LM Studio for scenarios 1 and 3; the rest verified with the fake server, see quickstart.md)
- [X] T058 Run ruff and the full pytest suite; fix all findings
- [X] T059 Verify Success Criteria SC-004 (every version traceable: model, prompt, timestamp, validation) and SC-007 (no task left in RUNNING after failures) with a checking script `tests/integration/test_success_criteria.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: なし。すぐ開始可
- **Foundational (Phase 2)**: Setup 完了後。全ストーリーをブロック
- **US1 (Phase 3)**: Foundational 後。他ストーリーへの依存なし（MVP）
- **US2 (Phase 4)**: Foundational 後。実行部分（T028）を再利用するため US1 の後を推奨
- **US3 (Phase 5)**: US1 の選択ロジック（T025）を拡張するため US1 の後
- **US4 (Phase 6)**: Foundational 後。`show` は US2 の検証保存（T036）を使う
- **Polish (Phase 7)**: 対象ストーリー完了後

### Within Each Story

- テスト → モデル → サービス → MCP/CLI の順
- テストは先に書き、失敗を確認してから実装

### Parallel Opportunities

- Phase 1: T003, T004, T005
- Phase 2: T007〜T011, T015〜T018（T006 は他と並列可）
- US1 テスト: T019〜T023、実装: T024, T026, T027
- US2 テスト: T031〜T035、US3 テスト: T041〜T043、US4 テスト: T048〜T050
- 単一開発者では Phase 順（P1 → P2 → P3）に進める

---

## Parallel Example: Foundational Models

```text
Task: "Implement ModelDefinition in src/ai_orchestrator/models/model_definition.py"
Task: "Implement Task and TaskState in src/ai_orchestrator/models/task.py"
Task: "Implement ArtifactVersion in src/ai_orchestrator/models/artifact.py"
Task: "Implement ValidationResult and RevisionRequest in src/ai_orchestrator/models/validation.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 のみ)

1. Phase 1 Setup（約30分）
2. Phase 2 Foundational（T006 のLM Studio確認を最初に行う）
3. Phase 3 US1
4. **STOP and VALIDATE**: quickstart シナリオ 1, 2, 8 を実行
5. Claude に接続して実タスクを1件通す

### Incremental Delivery

1. Setup + Foundational → 基盤完了
2. US1 → 検証 → MVP
3. US2 → 検証 → 修正ループ（システムの中核価値）
4. US3 → 検証 → モデル交換
5. US4 → 検証 → 運用性・復旧

---

## Notes

- [P] = 別ファイル・依存なし
- [Story] ラベルで仕様書との対応を追跡
- 同じファイルを触るタスク（`mcp_server.py`, `cli.py`, `selection.py`）は並列にしない
- 各タスクまたは論理グループごとにコミット
- 画像生成バックエンドは v1 対象外（`unsupported_backend` を返すのみ）
