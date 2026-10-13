# 智能建造 2040 技术预测系统（重构版）

单一路径、LangGraph 编排、科研风单页前端。

## 架构

```
前端 (React + Vite + ECharts)  :5173
        │  /api/health /api/topics /api/forecast /api/forecast/{id}[/result]
        ▼
FastAPI (src/api/app.py)
        │
        ▼
LangGraph 编排 src/forecast/graph.py  —— Think-and-Execute
   prepare → execute(并行9主题预测) → think(科学评审)
          →[有问题?]→ revise(修正一次) → roadmap(2030/2035/2040)
          → synthesize(新范式) → done
        │
        ▼
DeepSeek (OpenAI 兼容, 结构化 JSON 输出)
```

- **范式**：Think-and-Execute。Executor 产出预测，Critic 反思找过度断言，最多修正一轮，再生成路线图与全局综合。
- **证据**：`data/seed/topics.json`（9 个智能建造主题 + IPC 专利网络演化）。
- **存储**：`var/jobs/{job_id}/job.json` + `result.json`，无 SQLite、无项目/证据包/审批流程。

## 启动

```bash
# 1. 后端（首次需 .venv，已在项目内）
. .venv/bin/activate
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload

# 2. 前端（新终端）
cd frontend && npm run dev
```

浏览器打开 http://127.0.0.1:5173 ，点击「运行预测」。

> 需要 `.env` 中配置有效的 `DEEPSEEK_API_KEY`。一次完整预测会并行调用约 9 次预测 + 9 次评审 + 9 次路线图 + 1 次综合，约 1–3 分钟。

## 关键文件

| 作用 | 路径 |
|------|------|
| 编排图 | `src/forecast/graph.py` |
| 结构化模型 | `src/forecast/schemas.py` |
| LLM 调用 | `src/forecast/llm.py` |
| 提示词 | `src/forecast/prompts.py` |
| 任务服务 | `src/forecast/service.py` |
| API | `src/api/app.py` |
| 前端单页 | `frontend/src/App.tsx` |
| 图表 | `frontend/src/components/Charts.tsx` |

旧版多轮 round1/2/3、library、project、SQLite 等模块仍在仓库中但已不被新入口引用。
