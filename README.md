# AI Orchestrator

Claude を統括役、LM Studio 上のローカルモデルを専門サブエージェントとして使うための MCP サーバーです。
Claude がタスクを作り、モデルが自動選択され、生成された成果物をバージョン付きファイルで保存し、
Claude の検証 → 修正ループを経て完了します。

設計: [`specs/001-local-ai-orchestration/`](specs/001-local-ai-orchestration/)（spec / plan / tasks）

## セットアップ

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m ai_orchestrator.cli check-models   # config/models.yaml を検証
lms server start                                            # LM Studio のローカルサーバー
```

Claude への登録手順は [docs/mcp-setup.md](docs/mcp-setup.md)。

## 使い方（Claude から）

| ツール | 役割 |
|--------|------|
| `create_task` | タスク作成（`required_capabilities` を指定） |
| `select_model` | 能力・優先度・コンテキスト長・VRAM からモデルを選ぶ |
| `run_agent` | PENDING のタスクを実行し、成果物 v001 を保存 |
| `get_artifact` | 成果物と検証結果を取得 |
| `validate_artifact` | Claude の判定（pass / fail + 問題点）を登録 |
| `request_revision` | `minor`（軽微修正）/ `regenerate`（再生成）/ `switch_model`（別AI） |
| `complete_task` | 合格した版で完了し `workspace/artifacts/` へ配置 |

入出力の詳細: [contracts/mcp-tools.md](specs/001-local-ai-orchestration/contracts/mcp-tools.md)

## モデル定義 `config/models.yaml`

編集すると次のタスクから反映されます（再起動不要）。進行中のタスクは開始時の定義を使い続けます。
スキーマ: [model-definition.schema.json](specs/001-local-ai-orchestration/contracts/model-definition.schema.json)

`lmstudio_id` は `lms ls` の model key と一致させてください。`launch.method`:

- `jit`: 最初のリクエストで LM Studio が自動ロード（コンテキスト長は LM Studio の既定）
- `lms_cli`: `lms load` で明示ロード。`context_length` でロード時のコンテキスト長を指定

### Capabilities

能力名は自由文字列ですが、綴り違いは `no_capable_model` になります。推奨語彙:

`story` / `character_design` / `worldbuilding` / `analysis` / `code` / `review`

### 推論モデルの注意

Qwen3.x などの推論モデルは、思考で `max_tokens` を使い切ると回答が空になります。
その場合は `invalid_output`（`raise recommended_settings.max_tokens`）で失敗します。
`max_tokens` は十分大きく（例: 4096 以上）設定してください。

## タスクの確認・操作（CLI）

```powershell
.venv\Scripts\python -m ai_orchestrator.cli list            # 一覧（FAILED は原因付きで強調）
.venv\Scripts\python -m ai_orchestrator.cli show TASK-001   # 状態履歴・版・検証結果
.venv\Scripts\python -m ai_orchestrator.cli retry TASK-001  # retryable な FAILED を PENDING に戻す
```

## 成果物ファイル

`workspace/tasks/TASK-001/` に `task.json`, `prompt*.txt`, `result_vNNN.*`, `validation_vNNN.json` を保存します。
`result_vNNN.*` は直接編集できます。次回の読み込み時に `user_edit` の新しい版として取り込まれ、
AI が生成した版も残ります。

## v1 の制限

- 画像生成は未対応です。Animagine XL などの拡散モデルは LM Studio のチャット API では動きません。
  `model_type: image_gen` のモデルを選ぶと `unsupported_backend` で失敗します。
- モデルは逐次実行（同時ロード 1 モデル）、単一ユーザーです。

## テスト

```powershell
.venv\Scripts\python -m pytest            # LM Studio 不要（フェイクサーバーを自動起動）
.venv\Scripts\python -m ruff check src tests
```
