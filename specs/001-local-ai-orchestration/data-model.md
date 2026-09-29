# Data Model

## ModelDefinition（`config/models.yaml`）

| Field | Type | Rule |
|-------|------|------|
| id | string | 一意。システム内の識別子 |
| lmstudio_id | string | LM Studio上のモデル識別名 |
| display_name | string | 表示名 |
| capabilities | string[] | 1件以上。例: story, character_design, worldbuilding, analysis, code, review |
| priority | int | 0–100、高いほど優先 |
| max_context | int | > 0（トークン） |
| required_vram_gb | number | ≥ 0 |
| recommended_settings | object | temperature, top_p, max_tokens など |
| output_format | enum | text / json / code / image |
| model_type | enum | llm / vision / image_gen |
| launch | object | ロード方法（jit / lms_cli など） |
| enabled | bool | falseなら選択対象外（FR-014） |

検証: `id` 重複禁止。`capabilities` 空禁止。`model_type=image_gen` は v1 では登録可能だが実行時は「未対応バックエンド」エラー（research R4）。

## Task（`tasks/TASK-NNN/task.json`）

| Field | Type | Rule |
|-------|------|------|
| task_id | string | `TASK-` + 3桁以上の連番、一意（FR-001） |
| request | string | ユーザー依頼内容 |
| required_capabilities | string[] | 1件以上 |
| state | enum | 下記の状態 |
| state_history | {state, at, reason}[] | 追記のみ（FR-011） |
| selected_model_id | string? | 現在の担当モデル |
| selection_reason | string? | 選択理由 |
| model_snapshot | object? | タスク開始時点の選択モデル定義のコピー。models.yaml が後で変更されても進行中タスクは影響を受けない（FR-014） |
| category | string | 成果物の配置先。`required_capabilities` の先頭要素から決定（例: character_design → `artifacts/character_design/`） |
| excluded_model_ids | string[] | 引き継ぎで除外済み |
| revision_count | int | 上限 `max_revisions`（既定3） |
| max_revisions | int | 設定可 |
| versions | string[] | ArtifactVersion への参照 |
| final_version | string? | COMPLETED時に確定 |
| error | {kind, message, retryable}? | FAILED時 |
| created_at / updated_at | datetime | |

### 状態遷移

```text
PENDING ──run──▶ RUNNING ──生成完了──▶ REVIEWING
REVIEWING ──pass登録 + complete_task──▶ COMPLETED
REVIEWING ──不合格──▶ REVISION_REQUIRED ──request_revision──▶ RETRYING ──▶ RUNNING
任意（COMPLETED除く）──障害/上限超過──▶ FAILED
FAILED ──retryable かつ ユーザー操作──▶ PENDING
```

不正な遷移は拒否する。COMPLETED は合格判定済みの版が存在する場合のみ（FR-020）。

## ArtifactVersion（`result_vNNN.*`）

| Field | Type | Rule |
|-------|------|------|
| version | int | 1から連番、欠番なし、上書き禁止（FR-006） |
| model_id | string? | ユーザー編集版は null |
| kind | enum | initial / minor_revision / regenerate / model_switch / user_edit |
| prompt_file | string | 使用プロンプトの参照 |
| content_file | string | 成果物ファイル |
| content_hash | string | 保存時の内容SHA-256。手編集の検出に使う（contracts/task-files.md rule 3） |
| parent_version | int? | 修正元 |
| created_at | datetime | |

## ValidationResult（`validation_vNNN.json`）

| Field | Type | Rule |
|-------|------|------|
| version | int | 対象の版 |
| verdict | enum | pass / fail |
| issues | {aspect, description, severity}[] | fail時は1件以上 |
| aspects_checked | string[] | 要求充足, 必須項目, 整合性, 形式, 品質 など |
| recommended_action | enum? | minor / regenerate / switch_model（fail時） |
| created_at | datetime | |

## RevisionRequest

| Field | Type | Rule |
|-------|------|------|
| task_id | string | |
| base_version | int | 修正元 |
| method | enum | minor / regenerate / switch_model |
| instructions | string | 問題点を整理した指示 |
| target_model_id | string? | switch_model 時（省略で自動選択） |

## 関係

- Task 1 ── * ArtifactVersion 1 ── 0..* ValidationResult
- Task * ── 1 ModelDefinition（現在の担当）／ ArtifactVersion * ── 0..1 ModelDefinition（生成元）
