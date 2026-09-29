# Implementation Plan: ローカルAIサブエージェント統括システム

**Branch**: `001-local-ai-orchestration` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-local-ai-orchestration/spec.md`

## Summary

Claude を統括役、LM Studio 上のローカルモデルを専門サブエージェントとして使う。両者の間に **AI Orchestrator**（MCPサーバー）を置き、タスク作成・モデル選択・実行・成果物保存・検証結果登録・修正依頼・完了の7ツールをClaudeへ公開する。成果物とタスク記録はファイル（`tasks/`, `artifacts/`）として保存し、バージョンを上書きしない。モデル定義は設定ファイルで管理し、再ビルドなしで変更できる。技術方針は [research.md](research.md) を参照。

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: MCP Python SDK（FastMCP, stdio）, httpx（LM Studio REST）, pydantic v2（スキーマ検証）, PyYAML（モデル定義）, filelock（ファイル排他）

**Storage**: ローカルファイル（JSON/テキスト）。タスク単位ディレクトリ + 原子的書き込み（一時ファイル → rename）

**Testing**: pytest, pytest-asyncio, respx（LM Studio HTTPモック）。契約テスト + 結合テスト（フェイクLM Studioサーバー）

**Target Platform**: Windows 11（ローカル）。クロスプラットフォームのコードを維持

**Project Type**: MCPサーバー + 補助CLI（library + cli）

**Performance Goals**: Orchestrator自体のオーバーヘッド（状態更新・保存）は1操作あたり体感即時（<100ms）。生成時間はモデル依存で対象外

**Constraints**: 逐次実行（同時ロード1モデル）、VRAM上限に合わせたモデル選択、生成タイムアウト（既定300秒、設定可）、外部ネットワーク不要（完全ローカル）

**Scale/Scope**: 単一ユーザー、モデル定義 ~10件、タスク数千件、成果物は数KB〜数MBのテキスト

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` は未記入テンプレートのため、適用される原則・ゲートなし。**PASS（制約なし）**。

代わりに仕様書 §16 の設計方針を暫定ゲートとして使う:

| 方針 | 設計での担保 | 結果 |
|------|--------------|------|
| Claudeは統括、サブAIが生成 | Orchestratorは生成のみ担当、判定はClaudeが `validate_artifact` で登録 | PASS |
| モデル交換可能 | 選択ロジックはモデル定義のみ参照（FR-015） | PASS |
| 成果物中心・バージョン保持 | 追記のみ（append-only）の `result_vNNN` | PASS |
| 検証なしで完了不可 | `complete_task` は合格判定済み版が必要（FR-020） | PASS |
| ユーザー最終確認 | ユーザー編集版を `user_edit` 種別で保持 | PASS |

Phase 1 設計後の再評価: すべて PASS。

## Project Structure

### Documentation (this feature)

```text
specs/001-local-ai-orchestration/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── mcp-tools.md
│   ├── model-definition.schema.json
│   └── task-files.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/ai_orchestrator/
├── models/            # pydantic: Task, ModelDefinition, ArtifactVersion, ValidationResult, RevisionRequest
├── registry/          # モデル定義の読み込み・検索・能力マッチング・優先度選択
├── backends/          # LM Studio クライアント（chat, list, load/unload, timeout）
├── store/             # tasks/ artifacts/ のファイル入出力、原子的書き込み、排他
├── workflow/          # 状態遷移、修正ループ（minor/regenerate/switch_model）、上限管理
├── mcp_server.py      # 7ツールの公開
└── cli.py             # 状態一覧・履歴表示・モデル定義検証

config/
└── models.yaml        # モデル定義（ユーザー編集）

workspace/             # 実行時データ（gitignore対象）
├── tasks/TASK-001/{task.json,prompt.txt,result_v001.*,validation_v001.json}
└── artifacts/<category>/

tests/
├── contract/          # MCPツール入出力・スキーマ
├── integration/       # フェイクLM Studioでの依頼→検証→修正→完了
└── unit/              # 選択ロジック、状態遷移、ストア
```

**Structure Decision**: 単一プロジェクト（library + MCPエントリポイント + CLI）。Webフロントは作らず、ユーザーの閲覧・編集はCLIとファイル直接編集で行う（v1）。

## Complexity Tracking

違反なし（記載不要）。
