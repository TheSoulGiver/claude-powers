# Soul Memory Fabric

记忆控制平面微服务 — 统一 ingest / recall / consolidate / benchmark / SLO 能力。

## Quick Start

```bash
pip install -e ".[dev]"
uvicorn soul_fabric.api.routes:app --port 12393
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/memory/events` | 写入记忆事件 |
| POST | `/v1/memory/recall` | 多源召回 |
| POST | `/v1/memory/consolidate` | 记忆整理 |
| POST | `/v1/memory/reflect` | 程序性记忆 |
| POST | `/v1/memory/delete_user` | GDPR 删除 |
| GET | `/v1/memory/trace/{id}` | 审计追踪 |
| GET | `/v1/memory/coverage` | 能力覆盖报告 |
| GET | `/v1/memory/slo` | SLO 状态 |
| POST | `/v1/memory/benchmark` | 评测跑分 |
| GET | `/v1/memory/status` | 健康检查 |
