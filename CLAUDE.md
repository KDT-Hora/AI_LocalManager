# AIManager

Claude 統括 + LM Studio ローカルAIサブエージェントの MCP サーバー（Python 3.11、`src/ai_orchestrator/`）。

**最初に `docs/HANDOFF.md` を読むこと**（現状・次にやること・未対応事項）。

- テスト: `.venv\Scripts\python -m pytest -q`（LM Studio 不要）
- Lint: `.venv\Scripts\python -m ruff check src tests`
- 設計: `specs/001-local-ai-orchestration/`（Speckit で作成。tasks.md は全完了）
- モデル定義: `config/models.yaml`（編集すると次のタスクから反映）
- 使い方: `README.md`、MCP 登録: `docs/mcp-setup.md`
