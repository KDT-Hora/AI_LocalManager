# 引き継ぎ報告書（2026-09-29 時点）

## 次回、最初にやること（約3分）

1. `cd C:\Users\koyo\Downloads\AIManager`
2. `.venv\Scripts\python -m pytest -q` を実行する（70 passed になること）
3. `lms server start` を実行する
4. Claude Code を再起動し、`/mcp` で `ai-orchestrator` が connected であることを確認する
5. Claude に「キャラクターAの設定を作成して」と依頼し、実モデルで通しを確認する

`.venv` が無い環境では先に `python -m venv .venv` → `.venv\Scripts\python -m pip install -e ".[dev]"`。

## 何を作ったか

Claude を統括役、LM Studio 上のローカルモデルを専門サブエージェントにする MCP サーバー「AI Orchestrator」。
元の仕様案: `Claude_LMStudio_サブエージェントシステム仕様案.txt`

流れ: 依頼 → モデル自動選択 → 生成 → 成果物をバージョン付きで保存 → Claude が検証 → 修正ループ（軽微修正 / 再生成 / 別モデル）→ 完了。

## 現在の状態

| 項目 | 状態 |
|------|------|
| Speckit（specify → plan → tasks → analyze → implement） | 完了。全 59 タスク `[X]` |
| 自動テスト | 70 件すべて通過（LM Studio 不要、フェイクサーバー使用） |
| ruff | 問題なし |
| 実 LM Studio での通し | `qwen3.8-9b` で「依頼 → 生成 → 検証 → 完了」を確認 |
| MCP サーバー（stdio） | 7 ツールの登録と呼び出しを確認 |
| Claude Code からの実利用 | **未確認**（`.mcp.json` は作成済み） |

## 構成

| 場所 | 内容 |
|------|------|
| `src/ai_orchestrator/mcp_server.py` | 7 ツール（create_task, select_model, run_agent, get_artifact, validate_artifact, request_revision, complete_task） |
| `src/ai_orchestrator/workflow/service.py` | 7 操作の本体（`Orchestrator`） |
| `src/ai_orchestrator/registry/` | `models.yaml` の読み込み（再起動不要で反映）、モデル選択 |
| `src/ai_orchestrator/backends/lmstudio.py` | LM Studio 通信（REST 生成 + `lms` CLI でロード） |
| `src/ai_orchestrator/store/` | `workspace/tasks/TASK-NNN/` へのバージョン付き保存、手編集の取り込み |
| `src/ai_orchestrator/cli.py` | `check-models` / `list` / `show` / `retry` |
| `config/models.yaml` | モデル定義（現在: qwen-27b, qwen-9b, omnicoder-9b） |
| `specs/001-local-ai-orchestration/` | spec / plan / research / data-model / contracts / quickstart / tasks |
| `README.md`, `docs/mcp-setup.md` | 使い方、MCP 登録 |

## 実モデルで分かったこと（対応済み）

- Qwen3.8 は推論モデル。`max_tokens` を思考で使い切ると回答が空になる → `invalid_output`（max_tokens 引き上げの助言付き）として扱う。`max_tokens` は 4096 以上にすること。
- `lms load` の既定コンテキスト長は 4096 で `max_context` とは無関係。`launch.context_length` で指定する（`qwen-27b` は 16384 を指定済み。他は未指定）。
- `mcp` は 2.x で `FastMCP` が改名されたため `<2` に固定している。

## 未確認・未対応

1. Claude Code からの実利用（上の「最初にやること」）
2. 実モデルでの修正ループ（軽微修正 / 再生成 / 別モデル）。フェイクサーバーでのみ確認済み
3. SC-002（選択精度 95%）と SC-003（修正 3 回以内 80%）は未測定。実運用でしか測れない
4. **画像生成は v1 対象外**。Animagine XL などの拡散モデルは LM Studio では動かない。`model_type: image_gen` は `unsupported_backend` で失敗する。方針（別基盤を足すか、仕様から外すか）は未決定 → `specs/.../research.md` R4
5. `.specify/memory/constitution.md` は未記入のテンプレートのまま（`/speckit-constitution` で作成可）
6. `omnicoder-9b` の `context_length` は未指定。`lms_cli` で使う前に決める

## 次の候補（優先順）

1. 実利用の通し確認と、`models.yaml` の `max_tokens` / `context_length` の調整
2. 実モデルで修正ループを 1 回通す（`validate_artifact` fail → `request_revision`）
3. 画像生成の方針決定（未決定事項 4）
4. 並列実行や品質履歴など、仕様案 §17 の将来拡張

## 注意

- 前回、確認のため LM Studio のサーバーを起動しモデルを読み込んだ。作業後にアンロードしてサーバーを停止済み。
- `workspace/`（タスク・成果物・ログ）は `.gitignore` 対象。リポジトリには含まれない。
- `.mcp.json` にはこの PC 固定のパスが入っている。別マシンでは書き換えること。
