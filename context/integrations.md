# Integrations

| Integration | Progression | How |
|---|---|---|
| Amazon Bedrock | 1 (optional), 2 | `EDE_MODEL_PROVIDER=bedrock`, `EDE_MODEL_ID`, `AWS_REGION`; `pip install -r requirements-bedrock.txt` |
| Ollama (local open-weight model) | 1 (optional) | `EDE_MODEL_PROVIDER=ollama`, `OLLAMA_MODEL`; `pip install -r requirements-ollama.txt` |
| SQLite checkpointer | 1 | `langgraph-checkpoint-sqlite`, file at `$EDE_DATA_DIR/checkpoints.db` |
| DynamoDB checkpointer | 2 | to be selected or implemented |
| S3 report store | 2 | replaces `$EDE_DATA_DIR/reports/` |
