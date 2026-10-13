# 交互式技术预测工作台 - 技术设计

## Design Summary
新增一个轻量 Web/API 层，将现有脚本式智能建造预测系统包装成可交互工作台。整体设计遵循“预测内核不重写、输入层可审查、输出层学术化”的原则。

```text
研究文档/IPC分析/主题分析
        │
        ▼
文档解析与主题抽取
        │
        ▼
人工主题校准工作台
        │
        ▼
预测任务编排 API
        │
        ├── run_round1
        ├── run_round2
        ├── run_round3
        └── run_all_topics_roadmap
        │
        ▼
学术化结果展示与导出
```

## Existing Capabilities To Reuse
- `src/data_preparation/build_round1_inputs.py`: 构造第一轮主题输入。
- `src/llm_orchestrator/round1_runner.py`: 主题演化预测。
- `src/llm_orchestrator/round2_runner.py`: 新范式识别。
- `src/llm_orchestrator/round3_runner.py`: 全局技术路线图。
- `src/llm_orchestrator/per_topic_roadmap_runner.py`: 分主题路线图。
- `src/report/per_topic_roadmap_report.py`: 分主题报告和图表解释。
- `src/report/roadmap_charts.py`: TRL、里程碑、不确定性等图表生成。
- `src/evaluation/backtesting.py`: 回溯验证。
- `config/settings.py`: 功能开关和模型参数配置。

## Proposed Modules
### 1. API Layer
新增目录：

```text
src/api/
├── __init__.py
├── app.py
├── schemas.py
├── document_service.py
├── topic_service.py
├── forecast_service.py
└── storage.py
```

职责：
- `app.py`: FastAPI 应用入口和路由注册。
- `schemas.py`: Pydantic 请求/响应模型。
- `document_service.py`: 文档保存、读取、基础清洗。
- `topic_service.py`: 候选主题抽取、合并、编辑、输入转换。
- `forecast_service.py`: 预测任务创建、执行、状态更新、结果聚合。
- `storage.py`: 本地 JSON 或 SQLite 存储封装。

首版建议使用 FastAPI，原因：
- Python生态内与现有项目集成成本低。
- Pydantic 能明确约束主题输入和预测输出结构。
- 后续可自然接入异步任务或 WebSocket 进度推送。

### 2. Frontend Layer
新增目录：

```text
frontend/
├── package.json
├── src/
│   ├── api/
│   ├── components/
│   ├── pages/
│   ├── charts/
│   └── types/
└── index.html
```

推荐 React + TypeScript + ECharts。首版页面可以是单页工作台：
- 文档输入面板。
- 候选主题校准表。
- 预测配置面板。
- 任务进度面板。
- 结果可视化面板。
- 学术结论与导出面板。

## API Design
### Documents
#### `POST /api/documents`
提交研究文档。

Request:
```json
{
  "title": "智能建造技术研究文档",
  "content": "文档全文或摘要",
  "source_type": "text"
}
```

Response:
```json
{
  "document_id": "doc_20260724_001",
  "title": "智能建造技术研究文档",
  "status": "stored"
}
```

#### `GET /api/documents/{document_id}`
读取文档元数据和清洗后的文本。

### Topic Extraction
#### `POST /api/topics/extract`
从一个或多个文档中抽取候选技术主题。

Request:
```json
{
  "document_ids": ["doc_20260724_001"],
  "seed_topics": "use_existing",
  "extraction_mode": "rules_then_llm"
}
```

Response:
```json
{
  "candidate_topics": [
    {
      "topic_id": "topic_001",
      "topic_name": "装配式建筑技术",
      "keywords": ["预制", "构件", "安装"],
      "ipc_evidence": [
        {
          "ipc": "E04B-001",
          "trend": "度中心度0.1779",
          "quote": "涉及预制构件、工厂制造及现场安装。",
          "document_id": "doc_20260724_001"
        }
      ],
      "fusion_pairs": [
        {"ipc1": "E04B", "ipc2": "B28B", "prob": 0.76}
      ],
      "sample_abstracts": ["涉及预制构件、工厂制造及现场安装。"],
      "evidence_score": 78.0,
      "selected": true
    }
  ]
}
```

### Topic Calibration
#### `GET /api/topics`
获取当前候选主题列表。

#### `POST /api/topics`
人工新增主题。

#### `PATCH /api/topics/{topic_id}`
编辑主题名称、关键词、IPC证据、融合对、样本摘要和人工说明。

#### `POST /api/topics/normalize`
将已选主题转换为现有预测输入格式。

Response:
```json
{
  "round1_inputs": [
    {
      "topic_name": "装配式建筑技术",
      "keywords": ["预制", "构件", "安装"],
      "example": "钢结构装配式建筑技术",
      "ipc_trend": "E04B-001度中心度0.1779",
      "fusion_pairs": [{"ipc1": "E04B", "ipc2": "B28B", "prob": 0.76}],
      "sample_abstracts": "涉及预制构件、工厂制造及现场安装。"
    }
  ]
}
```

### Forecast Jobs
#### `POST /api/forecast/jobs`
创建并启动预测任务。

Request:
```json
{
  "topic_ids": ["topic_001", "topic_002"],
  "time_nodes": ["2030", "2035", "2040"],
  "options": {
    "enable_self_consistency": true,
    "enable_multi_agent_debate": true,
    "enable_multi_model": false,
    "enable_reasoning_chain": true,
    "enable_per_topic_roadmap": true,
    "force_rerun": false
  }
}
```

Response:
```json
{
  "job_id": "forecast_20260724_001",
  "status": "queued",
  "created_at": "2026-07-24T10:00:00"
}
```

#### `GET /api/forecast/jobs/{job_id}`
查询任务状态。

Response:
```json
{
  "job_id": "forecast_20260724_001",
  "status": "running",
  "current_stage": "round2",
  "progress": 0.55,
  "steps": [
    {"name": "topic_normalization", "status": "done"},
    {"name": "round1", "status": "done"},
    {"name": "round2", "status": "running"},
    {"name": "round3", "status": "pending"},
    {"name": "per_topic_roadmap", "status": "pending"},
    {"name": "report", "status": "pending"}
  ]
}
```

#### `GET /api/forecast/jobs/{job_id}/results`
获取结构化预测结果。

#### `GET /api/forecast/jobs/{job_id}/charts`
获取前端图表数据。

#### `GET /api/forecast/jobs/{job_id}/export?format=markdown`
导出结果。首版支持 `json` 和 `markdown`。

## Data Model
### CandidateTopic
```json
{
  "topic_id": "topic_001",
  "topic_name": "装配式建筑技术",
  "keywords": ["预制", "构件", "安装"],
  "example": "钢结构装配式建筑技术",
  "ipc_evidence": [],
  "ipc_trend": "E04B-001度中心度0.1779",
  "fusion_pairs": [],
  "sample_abstracts": [],
  "operator_notes": "",
  "evidence_score": 0,
  "selected": true
}
```

### ForecastResult
```json
{
  "job_id": "forecast_001",
  "time_nodes": ["2030", "2035", "2040"],
  "topics": [],
  "round1_results": [],
  "round2_result": {},
  "round3_result": {},
  "per_topic_roadmaps": [],
  "fusion_evolution": [],
  "confidence_summary": {},
  "uncertainty_summary": {},
  "reasoning_chain": [],
  "academic_conclusion": ""
}
```

## Topic Extraction Strategy
首版采用两阶段策略：

1. **规则抽取**
   - IPC模式：匹配 `G06F`、`G06N-003`、`E04B-001`、`B28B` 等格式。
   - 指标模式：匹配 `度中心度`、`中介中心度`、`融合概率`、`共现`。
   - 主题候选：从标题、段落首句、已有 `topics.json` 名称和关键词中召回。

2. **LLM校正**
   - 将规则抽取结果和原文片段交给LLM，要求输出候选主题结构。
   - 强制每个主题至少绑定一条证据片段。
   - 无证据主题默认标记为低置信度，需人工确认。

## Frontend UX Flow
```text
Step 1 文档输入
  上传/粘贴研究文档，显示解析后的文本片段。

Step 2 主题抽取
  自动生成候选主题，展示IPC、融合对、证据片段和证据强度。

Step 3 人工校准
  勾选、删除、合并、编辑、新增主题。

Step 4 预测配置
  选择增强功能，确认2030/2035/2040节点。

Step 5 执行预测
  展示任务状态、每轮进度、错误和重试入口。

Step 6 结果分析
  展示路线图、TRL曲线、融合网络、不确定性、证据链和结论。
```

## Chart Requirements
- **时间轴路线图**：按主题展示 2030/2035/2040 技术发展节点。
- **TRL演化曲线**：展示每个主题从基线到 2040 的技术成熟度变化。
- **技术融合网络**：节点为技术主题或IPC，边为融合关系，权重为融合概率或证据强度。
- **不确定性热力图**：横轴为主题，纵轴为时间节点，颜色表示不确定性。
- **证据追溯表**：每条核心结论对应 IPC、文档片段、融合对和推理链条。

## Compatibility
- 不破坏 `python -m src.main`。
- 默认仍可从 `data/raw/topics.json` 和 `data/raw/high_potential_pairs.json` 构造输入。
- API创建的任务输出应保存到独立 job 目录，避免覆盖现有 `outputs/parsed` 缓存。
- 可复用现有输出作为前端演示数据。

## Storage Layout
建议首版使用本地文件：

```text
data/workbench/
├── documents/
├── topics/
└── jobs/
    └── forecast_20260724_001/
        ├── job.json
        ├── round1_results.json
        ├── round2_result.json
        ├── round3_result.json
        ├── per_topic_roadmaps.json
        ├── charts.json
        └── report.md
```

后续可将 `storage.py` 替换为 SQLite 实现。

## Error Handling
- 文档为空：返回 400，并提示上传或粘贴有效内容。
- 主题抽取无结果：返回空列表，并允许使用现有9个主题作为种子。
- LLM调用失败：记录失败步骤，任务状态设为 `failed` 或 `partial_failed`。
- 单主题失败：不中断其他主题，前端展示失败主题和重试入口。
- 图表生成失败：保留结构化结果，前端可使用 ECharts 数据兜底展示。

## Testing Strategy
- 单元测试：文档解析、IPC抽取、主题归一化、API schema 校验。
- 服务测试：预测任务创建、状态更新、结果读取、导出接口。
- 集成测试：使用 mock LLM 跑通文档到报告的完整流程。
- 前端测试：关键页面渲染、主题编辑、任务状态展示、图表数据适配。
- 回归测试：确保现有测试不受影响。
