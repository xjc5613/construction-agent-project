# 交互式技术预测工作台 - 实施计划

## [x] Task 1: 建立API基础结构与数据模型
- **Priority**: high
- **Depends On**: None
- **Description**:
  - 新增 `src/api/` 目录。
  - 创建 FastAPI 应用入口 `src/api/app.py`。
  - 创建 Pydantic schema：`DocumentCreate`、`DocumentInfo`、`CandidateTopic`、`ForecastJobCreate`、`ForecastJobStatus`、`ForecastResult`。
  - 新增本地存储封装 `src/api/storage.py`，首版支持 JSON 文件读写。
  - 新增配置项：工作台数据目录、是否启用API、默认时间节点。
- **Acceptance Criteria Addressed**: AC-1, AC-6, AC-10
- **Test Requirements**:
  - `programmatic` TR-1.1: FastAPI app 可以被测试客户端加载。
  - `programmatic` TR-1.2: schema 能校验合法和非法请求。
  - `programmatic` TR-1.3: storage 能创建、读取、更新 JSON 文件。
- **Notes**: 保持与现有 Python 项目风格一致，不引入重型框架。

## [x] Task 2: 实现研究文档输入与清洗接口
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - 实现 `POST /api/documents`。
  - 实现 `GET /api/documents/{document_id}`。
  - 支持粘贴文本和 `.txt/.md/.json` 文本型内容。
  - 保存原始内容、清洗内容、标题、来源类型和创建时间。
  - 对空文本、超长文本、编码异常提供清晰错误。
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `programmatic` TR-2.1: 可提交中文研究文档并返回 `document_id`。
  - `programmatic` TR-2.2: 可根据 `document_id` 读取文档。
  - `programmatic` TR-2.3: 空内容返回 400。
- **Notes**: 首版不处理PDF/Word，后续可扩展。

## [x] Task 3: 实现IPC与候选主题规则抽取
- **Priority**: high
- **Depends On**: Task 2
- **Description**:
  - 新增 `src/api/topic_service.py` 中的规则抽取函数。
  - 抽取 IPC 分类号、度中心度、中介中心度、融合概率、共现关系。
  - 使用现有 `data/raw/topics.json` 的主题名和关键词进行种子召回。
  - 从文档中截取证据片段，绑定到候选主题。
  - 生成初始 `evidence_score`。
- **Acceptance Criteria Addressed**: AC-2, AC-3
- **Test Requirements**:
  - `programmatic` TR-3.1: 能从包含 `E04B-001度中心度0.1779` 的文本中抽取IPC证据。
  - `programmatic` TR-3.2: 能根据“预制构件、工厂制造、现场安装”召回“装配式建筑技术”。
  - `programmatic` TR-3.3: 每个候选主题至少包含主题名、关键词、证据片段。
- **Notes**: 规则抽取先保证可控性，LLM校正可在后续任务接入。

## [x] Task 4: 实现LLM辅助主题校正
- **Priority**: medium
- **Depends On**: Task 3
- **Description**:
  - 新增主题抽取 prompt 模板，要求输出结构化 JSON。
  - 将规则抽取结果和原文片段作为上下文传给 LLM。
  - 要求 LLM 合并重复主题、补全关键词、提取 IPC 趋势、生成融合对候选。
  - 无明确证据的主题应标记为 `requires_review=true`。
  - 提供开关，允许仅使用规则抽取。
- **Acceptance Criteria Addressed**: AC-2, AC-3, AC-9
- **Test Requirements**:
  - `programmatic` TR-4.1: 使用 mock LLM 时能解析主题校正结果。
  - `programmatic` TR-4.2: LLM返回损坏JSON时能降级使用规则结果。
  - `human-judgement` TR-4.3: 主题合并和证据绑定结果可人工审查。
- **Notes**: 复用现有 `LLMClient`，不新增模型客户端。

## [x] Task 5: 实现主题校准API
- **Priority**: high
- **Depends On**: Task 3
- **Description**:
  - 实现 `POST /api/topics/extract`。
  - 实现 `GET /api/topics`。
  - 实现 `POST /api/topics` 人工新增主题。
  - 实现 `PATCH /api/topics/{topic_id}` 编辑主题。
  - 实现 `POST /api/topics/normalize`，将已选主题转换为现有 round1 输入格式。
- **Acceptance Criteria Addressed**: AC-2, AC-4
- **Test Requirements**:
  - `programmatic` TR-5.1: 能从文档生成候选主题列表。
  - `programmatic` TR-5.2: 能编辑主题关键词、IPC证据和融合对。
  - `programmatic` TR-5.3: normalize 输出字段兼容 `build_round1_inputs` 生成的结构。
- **Notes**: normalize 是连接前端校准与现有预测内核的关键边界。

## [x] Task 6: 实现预测任务编排服务
- **Priority**: high
- **Depends On**: Task 5
- **Description**:
  - 新增 `src/api/forecast_service.py`。
  - 实现 `POST /api/forecast/jobs`。
  - 实现 `GET /api/forecast/jobs/{job_id}`。
  - 将选中主题输入传给 `run_round1`、`run_round2`、`run_round3` 和 `run_all_topics_roadmap`。
  - 写入任务阶段状态：topic_normalization、round1、round2、round3、per_topic_roadmap、report。
  - 支持 `force_rerun` 和现有增强功能开关。
- **Acceptance Criteria Addressed**: AC-5, AC-6, AC-10
- **Test Requirements**:
  - `programmatic` TR-6.1: 使用 mock runner 能跑通任务状态从 queued 到 completed。
  - `programmatic` TR-6.2: 单个主题失败时任务进入 `partial_failed`，其他主题继续。
  - `programmatic` TR-6.3: 默认CLI入口 `python -m src.main` 行为不变。
- **Notes**: 首版可同步执行；如果耗时过长，再引入后台线程或任务队列。

## [x] Task 7: 实现预测结果与图表数据接口
- **Priority**: high
- **Depends On**: Task 6
- **Description**:
  - 实现 `GET /api/forecast/jobs/{job_id}/results`。
  - 实现 `GET /api/forecast/jobs/{job_id}/charts`。
  - 聚合 round1、round2、round3、分主题路线图、置信度和不确定性。
  - 生成前端图表友好的 JSON：时间轴、TRL曲线、融合网络、不确定性热力图、证据追溯表。
  - 结果层突出 2030、2035、2040，保留 2025 作为基线。
- **Acceptance Criteria Addressed**: AC-6, AC-7, AC-8
- **Test Requirements**:
  - `programmatic` TR-7.1: charts 返回包含 timeline、trl_series、fusion_network、uncertainty_heatmap。
  - `programmatic` TR-7.2: 结果中的核心结论能关联 evidence 或 reasoning_chain。
  - `programmatic` TR-7.3: 缺少图表文件时仍返回结构化兜底数据。
- **Notes**: 现有 matplotlib 图表可继续用于报告，前端图表使用结构化数据。

## [x] Task 8: 实现学术报告导出接口
- **Priority**: medium
- **Depends On**: Task 7
- **Description**:
  - 实现 `GET /api/forecast/jobs/{job_id}/export`。
  - 首版支持 `format=json` 和 `format=markdown`。
  - Markdown 报告包含：摘要、数据来源、方法说明、主题预测、2030/2035/2040路线图、技术融合变化、不确定性分析、结论、局限性。
  - 复用现有报告生成逻辑，必要时新增工作台报告生成函数。
- **Acceptance Criteria Addressed**: AC-8, AC-9
- **Test Requirements**:
  - `programmatic` TR-8.1: 可导出 JSON 结果包。
  - `programmatic` TR-8.2: 可导出 Markdown 报告。
  - `human-judgement` TR-8.3: 报告具有学术结构，证据与结论对应清晰。
- **Notes**: PDF/Docx 作为后续迭代。

## [x] Task 9: 创建前端工作台基础页面
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - 新增 `frontend/` 项目。
  - 搭建 React + TypeScript 基础结构。
  - 实现 API client 和类型定义。
  - 创建主工作台页面布局：文档输入、主题校准、预测配置、任务进度、结果展示。
  - 保持中文学术风格，避免过度装饰。
- **Acceptance Criteria Addressed**: AC-1, AC-4, AC-7
- **Test Requirements**:
  - `programmatic` TR-9.1: 前端项目可安装依赖并启动。
  - `programmatic` TR-9.2: API client 类型与后端 schema 对齐。
  - `human-judgement` TR-9.3: 页面信息层级清晰，适合研究工作流。
- **Notes**: 可先用 Vite；不影响 Python 后端。

## [x] Task 10: 实现文档输入与主题校准前端
- **Priority**: high
- **Depends On**: Task 5, Task 9
- **Description**:
  - 文档输入面板：粘贴文本、提交文档、显示 document_id。
  - 主题抽取按钮：调用 `/api/topics/extract`。
  - 候选主题表：展示主题名、关键词、IPC、融合对、证据片段、证据强度、是否选中。
  - 支持编辑、新增、删除、勾选和合并主题。
  - 主题校准完成后调用 normalize。
- **Acceptance Criteria Addressed**: AC-2, AC-3, AC-4
- **Test Requirements**:
  - `programmatic` TR-10.1: 输入文档后可显示候选主题。
  - `programmatic` TR-10.2: 编辑主题后请求体正确。
  - `human-judgement` TR-10.3: 操作者能清晰看到每个主题的证据来源。
- **Notes**: 这是该工作台相对现有系统的核心新增能力。

## [x] Task 11: 实现预测配置与任务进度前端
- **Priority**: high
- **Depends On**: Task 6, Task 9
- **Description**:
  - 预测配置面板：固定展示 2030、2035、2040 节点。
  - 提供增强功能开关：自洽性、多Agent、多模型、推理链条、分主题路线图。
  - 创建任务并展示 job_id。
  - 轮询任务状态，展示阶段进度和失败信息。
  - 支持失败后重试任务或重跑单主题。
- **Acceptance Criteria Addressed**: AC-5, AC-6
- **Test Requirements**:
  - `programmatic` TR-11.1: 可创建预测任务。
  - `programmatic` TR-11.2: 任务状态能从后端轮询并更新页面。
  - `human-judgement` TR-11.3: 进度表达清晰，用户知道当前执行到哪一轮。
- **Notes**: 首版轮询即可，WebSocket 可后续补充。

## [x] Task 12: 实现结果图表与学术结论前端
- **Priority**: high
- **Depends On**: Task 7, Task 9
- **Description**:
  - 展示全局路线图和分主题路线图。
  - 使用 ECharts 展示时间轴、TRL曲线、技术融合网络、不确定性热力图。
  - 展示证据追溯表和推理链条。
  - 展示最终学术结论、方法说明和局限性。
  - 提供 JSON/Markdown 导出按钮。
- **Acceptance Criteria Addressed**: AC-7, AC-8, AC-9
- **Test Requirements**:
  - `programmatic` TR-12.1: 图表组件能消费 `/charts` 返回的数据。
  - `programmatic` TR-12.2: 导出按钮能调用 export 接口。
  - `human-judgement` TR-12.3: 图表能清晰表达 2030/2035/2040 技术发展融合变化。
- **Notes**: 中文长文本需要折叠、悬浮提示和详情抽屉。

## [x] Task 13: 集成测试与回归验证
- **Priority**: high
- **Depends On**: Task 1-12
- **Description**:
  - 增加后端 API 测试。
  - 增加文档到报告的端到端 mock 测试。
  - 增加前端关键组件测试或轻量 smoke test。
  - 运行现有测试，确认无回归。
  - 更新 README，说明如何启动 API 和前端。
- **Acceptance Criteria Addressed**: AC-10
- **Test Requirements**:
  - `programmatic` TR-13.1: 后端新增测试通过。
  - `programmatic` TR-13.2: 现有测试通过。
  - `programmatic` TR-13.3: 前端构建通过。
  - `human-judgement` TR-13.4: README 能指导用户完成本地启动。
- **Notes**: 不要求真实 LLM 调用测试，使用 mock 保持稳定。
