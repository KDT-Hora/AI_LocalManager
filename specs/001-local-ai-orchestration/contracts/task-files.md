# Contract: 保存ファイル形式

ユーザーが直接開いて編集できることが要件（FR-017）。書き込みは追記のみ、既存版は上書きしない。

```text
workspace/
├── tasks/
│   └── TASK-001/
│       ├── task.json              # Task（data-model.md 参照）。状態・履歴・選択理由
│       ├── prompt.txt             # 初回プロンプト
│       ├── prompt_v002.txt        # 修正・再生成時のプロンプト
│       ├── result_v001.<ext>      # 成果物（拡張子は output_format による: txt/md/json/py 等）
│       ├── result_v001.meta.json  # ArtifactVersion（model_id, kind, created_at, parent_version）
│       ├── result_v002.<ext>
│       ├── result_v002.meta.json
│       ├── validation_v001.json   # ValidationResult
│       └── validation_v002.json
└── artifacts/
    └── <category>/                # complete_task 時に最終版をコピー（category = Task.category = 先頭の必要能力）
        └── <name>_<task_id>.<ext>
```

## ルール

1. `result_vNNN` の NNN は1から連番、欠番なし。
2. `*.json` は UTF-8（BOMなし）、一時ファイル → rename で原子的に書く。
3. ユーザーがファイルを直接編集した場合は、次回読込時に内容ハッシュ差分を検出し `kind=user_edit` の新しい版として取り込む（元の AI 生成版は残す）。
4. `task.json` の `state_history` は追記のみ。
5. 破損した JSON を検出したらタスクを FAILED にせず読み取り専用として報告する（データ保護優先）。
