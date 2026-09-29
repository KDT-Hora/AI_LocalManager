# Research: ローカルAIサブエージェント統括システム

NEEDS CLARIFICATION は残っていません。以下は技術選定の記録です。

> 注意: LM Studio の API 詳細（REST の load/unload エンドポイントの有無・パス、JIT ロード挙動）はバージョンで変わります。実装開始時に手元の LM Studio バージョンで確認し、確認結果を `backends/` のコメントに残すこと（tasks の最初のタスクにする）。

## R1. 実装言語

- **Decision**: Python 3.11+
- **Rationale**: MCP公式SDK（FastMCP）が成熟、HTTP/JSON/ファイル処理が簡潔、pydanticでスキーマ検証できる。
- **Alternatives**: TypeScript（MCP SDKあり、型は強いがpydantic相当の実行時検証が別途必要）／C#（ユーザーがUnity系環境だが、MCP SDKと保守性で劣後）。

## R2. Claudeとの接続

- **Decision**: MCPサーバー（stdio）として実装し、7ツールを公開。
- **Rationale**: 仕様案 §12 の方針。Claude Code / Desktop から設定だけで接続できる。
- **Alternatives**: HTTPサーバー（常駐が必要）、CLI呼び出し（構造化応答・ツール検出が弱い）。

## R3. LM Studio との通信

- **Decision（2026-09-29 に手元の `lms` CLI で確認済み）**: 生成は OpenAI互換REST（`POST /v1/chat/completions`）を httpx で呼ぶ。ロード/アンロードは `launch.method` で切り替える。`jit` は初回リクエストで LM Studio が自動ロードするため明示ロード不要。`lms_cli` は `lms load <key> --identifier <key> -y [-c <context_length>]` / `lms unload <id>` / `lms ps --json` を使う。ローカルサーバーは `lms server start` で起動が必要。
- **Rationale**: 互換APIは安定しており、モデル識別名を指定すれば生成できる。ロード操作だけをバックエンド層（`backends/lmstudio.py`）に閉じ込めたので、方式変更が他へ波及しない。
- **実測で分かったこと**: Qwen3.x は推論モデルで、`max_tokens` を思考で使い切ると `content` が空になる（`reasoning_content` のみ）。これを `invalid_output`（max_tokens 引き上げの助言付き）として扱う。`lms load` の既定コンテキスト長は 4096 で `max_context` とは無関係のため、`launch.context_length` で指定できるようにした。
- **Alternatives**: LM Studio SDK（言語依存）、llama.cpp直接（LM Studioを基盤にする方針に反する）。

## R4. 画像生成モデル（重要）

- **Decision**: v1では画像生成をバックエンド差し替え可能な拡張点として設計のみ行い、実装はテキスト生成に限定する。
- **Rationale**: 仕様案の Animagine XL は拡散モデルで、LM Studio のチャット系APIでは実行できない。実行には別基盤（ComfyUI/Stable Diffusion WebUI等）が必要で、仕様案「LM Studioを実行基盤にする」と食い違う。
- **Alternatives**: 画像用バックエンドをv1で追加（スコープ増）／画像を仕様から削除（将来拡張を失う）。
- **要ユーザー確認**: 画像バックエンドの方針（次フェーズ前に確認推奨、ブロッカーではない）。

## R5. モデル定義の保存

- **Decision**: `config/models.yaml` を pydantic で検証。ファイル変更を各タスク開始時に再読込。
- **Rationale**: 再ビルド不要（FR-014）、手編集しやすい、JSON Schemaを契約として提供できる。
- **Alternatives**: DB（過剰）、JSON（コメント不可で編集性が低い）。

## R6. モデル選択アルゴリズム

- **Decision**: (1) 有効モデルのみ → (2) 必要能力をすべて含む → (3) 入力トークン見積り ≤ max_context（見積り = 入力文字数 ÷ 2 を切り上げ。日本語で過小評価しない保守的近似。出力用に `max_tokens` 分の余裕も加算） → (4) 必要VRAM ≤ 設定VRAM上限 → (5) priority降順、同点は現在ロード済みを優先（切替コスト削減）。別モデル引き継ぎ時は直前までに使ったモデルを除外。
- **Rationale**: 決定的で説明可能。選択理由を `task.json` に記録できる。
- **Alternatives**: 学習型選択（仕様案の将来拡張）。

## R7. 成果物・タスクの保存と排他

- **Decision**: `workspace/tasks/TASK-NNN/` にバージョン付きファイルを追記のみで保存。書き込みは一時ファイル → rename。タスク単位のファイルロック。
- **Rationale**: 上書き禁止（FR-006）、中断時の破損防止（FR-019）、同時書き込み防止（Edge Case）。
- **Alternatives**: SQLite（照会は楽だが、ユーザーが成果物を直接編集する運用と相性が悪い）。

## R8. 状態遷移

- **Decision**: 明示的な遷移表を持ち、不正遷移は拒否。PENDING → RUNNING → REVIEWING → (COMPLETED | REVISION_REQUIRED) → RETRYING → RUNNING …、任意の段階から FAILED。遷移ごとに履歴へ追記。
- **Rationale**: 仕様 FR-011。テスト容易。
- **Alternatives**: 暗黙状態（追跡不能）。

## R9. 障害処理と再開

- **Decision**: LM Studio接続不可・ロード失敗・タイムアウト・不正出力を型付きエラーにし、`task.json` に原因を記録。起動時に RUNNING のまま残ったタスクを検出し、FAILED（再試行可能フラグ付き）へ移す。
- **Rationale**: FR-012, FR-013, FR-019。無反応タスクを残さない（SC-007）。

## R10. テスト戦略

- **Decision**: フェイクLM Studioサーバー（OpenAI互換のスタブ）で結合テスト。実モデルを使う確認は quickstart の手動シナリオ。
- **Rationale**: 品質ばらつきの大きい実モデルに依存せず、決定的に検証できる。
