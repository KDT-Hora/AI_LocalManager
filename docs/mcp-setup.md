# MCP 登録

## Claude Code

プロジェクトルート（このリポジトリ）の `.mcp.json`:

```json
{
  "mcpServers": {
    "ai-orchestrator": {
      "command": "C:\\Users\\koyo\\Downloads\\AIManager\\.venv\\Scripts\\python.exe",
      "args": ["-m", "ai_orchestrator.mcp_server"],
      "cwd": "C:\\Users\\koyo\\Downloads\\AIManager",
      "env": {
        "AIO_MODELS": "config/models.yaml",
        "AIO_WORKSPACE": "workspace"
      }
    }
  }
}
```

または: `claude mcp add ai-orchestrator -- C:\Users\koyo\Downloads\AIManager\.venv\Scripts\python.exe -m ai_orchestrator.mcp_server`

## 環境変数

| 名前 | 既定値 | 内容 |
|------|--------|------|
| `AIO_MODELS` | `config/models.yaml` | モデル定義ファイル |
| `AIO_WORKSPACE` | `workspace` | タスク・成果物の保存先 |
| `AIO_LMSTUDIO_URL` | `http://localhost:1234` | LM Studio サーバー |
| `AIO_TIMEOUT` | `300` | 生成のタイムアウト（秒） |
| `AIO_LOAD_TIMEOUT` | `600` | `lms load` のタイムアウト（秒） |
| `AIO_MAX_REVISIONS` | `3` | 修正回数の上限 |
| `AIO_LMS_BIN` | PATH 上の `lms` | `lms` CLI のパス（`launch.method: lms_cli` 用） |

## 注意

- stdout は MCP の通信路です。ログは stderr と `workspace/orchestrator.log` に出ます。
- サーバー起動時に、前回中断された RUNNING / RETRYING のタスクを FAILED（retryable）へ移します。
