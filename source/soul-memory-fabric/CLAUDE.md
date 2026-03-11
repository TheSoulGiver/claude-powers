# Soul Memory Fabric

独立记忆控制平面微服务，从 ling-platform 提取。

## 架构

- `src/soul_fabric/` — 核心包
  - `config.py` — FabricConfig，环境变量驱动
  - `service.py` — MemoryFabric 主服务（单例）
  - `store.py` — MongoDB 持久层（自带连接管理）
  - `atom.py` — MemoryAtom 核心数据结构
  - `models.py` — 能力模型（MemoryCapability, RecallRoutePlan 等）
  - `api_models.py` — REST API Pydantic 模型
  - `memguard.py` — 安全过滤（投毒检测 + 隔离）
  - `amem_evolution.py` — A-MEM 记忆演化
  - `catalog.py` / `planner.py` — Provider 注册与能力路由
  - `autotune.py` / `benchmark.py` — SLO 自动调参与评测
  - `letta_blocks.py` / `langmem_rules.py` — 可选集成
  - `utils.py` — 内联工具（validation, sensitivity, async_tasks）
  - `api/routes.py` — FastAPI 路由（独立微服务入口）

## 运行

```bash
# 安装
pip install -e ".[dev]"

# 独立启动
uvicorn soul_fabric.api.routes:app --port 12393

# 测试
pytest
```

## 环境变量

- `SOUL_ENABLED` — 总开关
- `SOUL_FABRIC_ENABLED` — Fabric 开关
- `MONGO_URL` — MongoDB 连接
- `MONGO_DB` — 数据库名
- `SOUL_AGENT_KEY` — API 认证密钥（可选）

## 集成模式

### 独立微服务
直接 `uvicorn soul_fabric.api.routes:app --port 12393`

### 作为 ling-platform 依赖
```python
from soul_fabric import MemoryFabric, FabricConfig
fabric = MemoryFabric(
    recall_fn=my_recall,
    consolidation_fn=my_consolidation,
    deletion_fn=my_deletion,
    provider_health_fn=my_health_check,
    warmup_fn=my_warmup,
)
```
