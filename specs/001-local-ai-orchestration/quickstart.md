# Quickstart: 動作確認ガイド

実装完了後に、エンドツーエンドで動くことを確認する手順です。コマンド名は実装時に確定します。

## 前提

- LM Studio が起動し、ローカルサーバーが有効（テキストLLMを1つ以上ダウンロード済み）
- Python 3.11+
- `config/models.yaml` に最低1モデルを登録（スキーマ: [contracts/model-definition.schema.json](contracts/model-definition.schema.json)）

## セットアップ

1. 依存関係をインストールする（例: `pip install -e .[dev]`）
2. `config/models.yaml` を検証する（例: `python -m ai_orchestrator.cli check-models`）
3. Claude に MCPサーバーを登録する（stdio、`python -m ai_orchestrator.mcp_server`）

## 検証シナリオ

各シナリオは [spec.md](spec.md) の受け入れシナリオに対応します。ツールの入出力は [contracts/mcp-tools.md](contracts/mcp-tools.md) を参照。

| # | シナリオ | 手順 | 期待結果 | 仕様 |
|---|----------|------|----------|------|
| 1 | 基本生成 | Claude に「キャラクターAの設定を作成して」と依頼 | `TASK-001` が作成され、`result_v001.*` と `task.json`（使用モデル・プロンプト・日時）が保存される | US1 |
| 2 | 対応モデルなし | 登録されていない能力（例: `nonexistent`）で依頼 | `no_capable_model` が返り、タスクは FAILED | US1-2 |
| 3 | 検証合格 | `validate_artifact` で pass → `complete_task` | 状態 COMPLETED、`artifacts/` に最終版が配置 | US2-1 |
| 4 | 軽微修正 | fail（issues付き）→ `request_revision(method=minor)` | `result_v002` 追加、`result_v001` は保持、`revision_count=1` | US2-2 |
| 5 | 再生成 / 別モデル | 2モデル登録し `regenerate`、`switch_model` を実行 | 新版が追加され、`switch_model` では別の `model_id` が記録される | US2-3,4 |
| 6 | 修正上限 | 不合格を4回繰り返す（既定上限3） | `revision_limit_reached`、状態 FAILED | US2-5 |
| 7 | モデル切替 | `models.yaml` で優先度変更、または `enabled: false` | 次のタスクから反映（再起動不要） | US3 |
| 8 | 障害 | LM Studio を停止して `run_agent` | `backend_unreachable`、タスクが RUNNING のまま残らない | Edge |
| 9 | 中断復旧 | 生成中にプロセスを強制終了 → 再起動 | RUNNING だったタスクが FAILED(retryable) になり、保存済み版は無傷 | FR-019 |
| 10 | ユーザー編集 | `result_vNNN` を手編集 → 状態確認 | `user_edit` の新版として取り込まれ、AI生成版も残る | US4 |

## 自動テスト

- `pytest tests/contract tests/unit`（LM Studio不要）
- `pytest tests/integration`（フェイクLM Studioサーバーを自動起動）

## 実行結果（T057, 2026-09-29）

| # | シナリオ | 結果 | 確認方法 |
|---|----------|------|----------|
| 1 | 基本生成 | OK | 実LM Studio（`qwen3.8-9b`, `lms_cli` ロード）。`result_v001.txt` と `task.json` を保存 |
| 3 | 検証合格 → 完了 | OK | 実LM Studio。`artifacts/character_design/` に配置 |
| 2, 4, 5, 6, 7, 8, 9, 10 | 対応モデルなし / 軽微修正 / 再生成・別モデル / 修正上限 / モデル定義変更 / 障害 / 中断復旧 / ユーザー編集 | OK | 自動テスト（フェイクLM Studio）`tests/integration/`。実モデルでは未実施 |

- MCP サーバーを stdio で起動し、`list_tools` / `create_task` / `select_model` の呼び出しを確認。
- 実モデルの初回実行は `max_tokens: 400` で `invalid_output`（推論だけで token を使い切った）。4000 にすると成功。README「推論モデルの注意」に記載。
- SC-002（選択精度95%）と SC-003（修正3回以内80%）は、実モデルでの継続的な運用でしか測れない。今回は測定していない。
