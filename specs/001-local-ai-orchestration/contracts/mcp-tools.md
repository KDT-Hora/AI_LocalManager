# Contract: MCP Tools

すべてのツールは JSON を返す。失敗時は `{ "ok": false, "error": { "kind", "message", "retryable" } }`。
`error.kind`: `no_capable_model` / `model_load_failed` / `backend_unreachable` / `timeout` / `invalid_output` / `invalid_transition` / `revision_limit_reached` / `not_found` / `unsupported_backend`。

## 呼び出し可能な状態

| ツール | 許可される状態 |
|--------|----------------|
| `run_agent` | PENDING のみ（修正の再生成は `request_revision` を使う） |
| `request_revision` | REVISION_REQUIRED、または REVIEWING（pass 済みの版をさらに直す場合） |
| `complete_task` | REVIEWING（指定版に pass 検証あり） |

上記以外の状態からの呼び出しは `invalid_transition`。

## create_task

| | |
|---|---|
| 入力 | `request: string`, `required_capabilities: string[]`, `max_revisions?: int`, `input_files?: string[]` |
| 出力 | `{ ok, task_id, state: "PENDING" }` |
| 副作用 | `tasks/TASK-NNN/task.json` と `prompt.txt` を作成 |

## select_model

| | |
|---|---|
| 入力 | `task_id`, `exclude_model_ids?: string[]` |
| 出力 | `{ ok, model_id, reason, candidates: [{model_id, priority, rejected_reason?}] }` |
| エラー | 条件を満たすモデルなし → `no_capable_model`（FR-002/003、タスクは FAILED） |

## run_agent

| | |
|---|---|
| 入力 | `task_id`, `model_id?`（省略時は自動選択）, `prompt?`（省略時は task の prompt） |
| 出力 | `{ ok, version, artifact_path, state: "REVIEWING" }` |
| 副作用 | 必要ならモデルをロード → 生成 → `result_vNNN` 保存。RUNNING → REVIEWING |
| エラー | `model_load_failed`, `backend_unreachable`, `timeout`, `invalid_output` |

## get_artifact

| | |
|---|---|
| 入力 | `task_id`, `version?`（省略で最新） |
| 出力 | `{ ok, version, model_id, kind, content, validation? }` |

## validate_artifact

Claude が判定した結果を登録する（Orchestratorは判定しない）。

| | |
|---|---|
| 入力 | `task_id`, `version`, `verdict: "pass" \| "fail"`, `aspects_checked: string[]`, `issues?: [{aspect, description, severity}]`, `recommended_action?: "minor" \| "regenerate" \| "switch_model"` |
| 出力 | `{ ok, state: "REVIEWING" \| "REVISION_REQUIRED" }`（pass時は状態を維持し complete_task を許可） |
| 検証 | fail時は `issues` 必須 |

## request_revision

| | |
|---|---|
| 入力 | `task_id`, `base_version`, `method: "minor" \| "regenerate" \| "switch_model"`, `instructions`, `target_model_id?` |
| 出力 | `{ ok, version, state: "REVIEWING" }` |
| 動作 | `revision_count` を加算。上限超過なら `revision_limit_reached` で FAILED。`minor`=既存版+指示、`regenerate`=最初から、`switch_model`=別モデルで生成 |

## complete_task

| | |
|---|---|
| 入力 | `task_id`, `version` |
| 出力 | `{ ok, state: "COMPLETED", final_version, artifact_path }` |
| 条件 | 指定版に `pass` の検証結果があること。なければ `invalid_transition`（FR-020）。成果物を `artifacts/<category>/` へも配置 |
