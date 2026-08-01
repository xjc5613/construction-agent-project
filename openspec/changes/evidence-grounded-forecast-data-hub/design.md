## Context

当前系统包含两条并行路径：

1. CLI 路径从 `data/raw/topics.json`、`high_potential_pairs.json` 和样例摘要构造固定输入。
2. 工作台路径将粘贴文本保存为 JSON，从材料中抽取候选主题，再调用相同的多轮预测内核。

工作台已经具备主题编辑、任务状态、2030/2035/2040 预测、分主题路线图和图片资产展示，但数据与证据层存在明显断点：

- `DocumentCreate` 只接收 JSON 文本，不是真正的文件上传。
- 所有工作台主题保存在同一个 `topics.json`，没有项目隔离。
- IPC 指标、融合关系和论文只是主题对象上的文本片段，没有可查询的数据集。
- 任务启动时不会根据最终主题再次检索基础数据。
- Round 2、Round 3 和分主题路线图只接收前序摘要，原始证据无法持续约束结论。
- JSON 文件存储不适合多数据集、全文检索、去重、版本和关联查询。
- 运行产物、种子数据、研究文档和工具资源混在仓库视野中，部分已忽略目录仍有历史文件被 Git 跟踪。

本项目定位为单机研究工作台，主要用户是智能建造技术预测研究人员。首要约束是可复现、可追溯和易于本地部署，而不是多租户、高并发或云服务扩展。

## Goals / Non-Goals

**Goals:**

- 建立长期维护的基础证据库，统一管理 IPC 时间序列、IPC 融合关系、论文文件与论文元数据。
- 支持 CSV、XLSX、JSON、PDF、DOCX、TXT、Markdown 导入，并给出可审查的字段映射、解析状态和错误信息。
- 将一次预测组织为独立项目，使材料、候选主题、确认主题、证据包和任务结果互相隔离。
- 在预测启动前对 IPC 与论文进行双通道检索，并冻结不可变证据快照。
- 让证据 ID 贯穿多轮预测、路线图、图表和最终结论。
- 对空结果、证据不足、解析失败和资产失败建立明确的质量门槛。
- 在现有 React 工作台中增加基础数据、证据审阅和学术分析页面，并拆分当前单文件组件。
- 保持固定种子数据、现有 CLI 和已完成结果资产 API 的兼容性。

**Non-Goals:**

- 不接入商业专利库、学术数据库或网络爬虫。
- 不建设分布式任务队列、多租户权限和在线协作。
- 不在首版引入向量数据库、知识图谱数据库或独立数据库服务。
- 不由大模型计算 IPC 统计指标；趋势值必须由确定性代码从导入数据计算。
- 不删除用户现有本地输出；资源整理仅调整目录、Git 跟踪和迁移入口。

## Decisions

### 1. 使用 SQLite + FTS5 作为证据库

结构化数据与检索索引保存于 `var/library/library.sqlite3`，原始文件保存于 `var/library/raw/`，解析文本保存于 `var/library/parsed/`。

核心表：

```text
datasets
├── dataset_id, kind, name, version, checksum, status, imported_at

source_files
├── file_id, dataset_id, filename, media_type, checksum, stored_path, parse_status

papers
├── paper_id, dataset_id, title, authors, year, doi, keywords, abstract, file_id

paper_chunks
├── chunk_id, paper_id, section, ordinal, content

ipc_metrics
├── dataset_id, ipc_code, year, patent_count, degree_centrality,
│   betweenness_centrality, growth_rate, source_row

ipc_fusions
├── dataset_id, ipc1, ipc2, year, probability, source_row

projects / project_materials / project_topics
evidence_packages / evidence_items / forecast_jobs
```

FTS5 索引覆盖论文题名、摘要、关键词和正文片段。选择 SQLite 的原因：

- Python 标准库原生支持，部署不需要独立服务。
- 事务、唯一约束和关联查询比 JSON 文件可靠。
- FTS5 足够支撑当前中文关键词、IPC 和主题术语召回。
- 数据量和并发规模尚不需要 Postgres 或向量数据库。

备选方案：

- 继续使用 JSON：实现简单，但无法可靠完成版本、去重、事务和跨数据集检索。
- 向量数据库：语义召回更强，但增加模型、索引和部署复杂度；可在后续以可插拔 reranker 增强。

### 2. 区分基础数据与本次项目材料

基础数据是长期存在、可版本化的证据集合；项目材料只定义一次预测的研究边界。两者不得写入同一实体。

```text
基础证据库                          预测项目
IPC数据集 / 论文数据集              文本 / 上传文件
        │                                │
        └───────── 主题证据检索 ─────────┘
                         │
                    证据快照
```

项目状态采用：

```text
draft → material_ready → topics_review → evidence_review
      → ready_to_forecast → forecasting → completed/failed
```

每个项目拥有独立材料、主题和任务；不再使用全局 `topics.json` 作为工作台事实来源。

### 3. 文件导入采用解析器注册表

新增 `src/ingestion/`，通过统一接口处理不同格式：

```python
parse(file_path, options) -> ParsedDocument | ParsedTable
```

- CSV：Python `csv`，支持 UTF-8/UTF-8-SIG，检测分隔符。
- XLSX：`openpyxl`，选择工作表并映射列。
- JSON：标准库 `json`，支持数组记录。
- PDF：`pypdf`，按页抽取文本；扫描 PDF 明确标记为不支持 OCR。
- DOCX：`python-docx`，抽取标题、段落和表格文本。
- TXT/Markdown：按受控编码读取。
- 文件上传：FastAPI `UploadFile` + `python-multipart`。

导入先进入 staging，再执行校验、预览和提交。表格必须显式映射到规范字段，错误行保留行号和原因，不能静默丢弃。

### 4. 主题抽取采用规则召回 + LLM 归纳 + 人工确认

规则层负责 IPC、年份、趋势指标、论文关键词和已知种子主题召回；LLM 只负责：

- 合并同义主题。
- 生成规范化主题名和关键词。
- 从明确片段中归纳主题描述。
- 标记歧义和待审内容。

LLM 不得生成不存在的 IPC、论文或统计值。候选主题保留 `source_material_ids` 和 `evidence_item_ids`。主题校准提供新增、编辑、删除、合并、归档和确认；删除采用项目内软删除，避免破坏已经存在的任务快照。

### 5. 双通道证据检索与不可变快照

确认主题后执行两个确定性检索器：

**IPC 检索器**

- 按主题关键词、材料中 IPC、同族上位分类召回 IPC 序列。
- 计算年度增长率、线性斜率、近年变化、变化点、中心度变化。
- 召回与主题相关的 IPC 融合边，并保留数据集版本和源行。

**论文检索器**

- 使用题名、摘要、关键词和正文 FTS 召回。
- 综合关键词匹配、IPC 共现、年份新鲜度和来源完整度排序。
- 返回论文元数据、引用信息和有限长度的证据片段。

检索结果形成可编辑 evidence package。用户可以排除弱相关证据或补充说明。启动任务时将其冻结为：

```text
var/jobs/<job_id>/evidence_snapshot.json
```

快照包含数据集版本、查询参数、IPC记录、论文引用、证据片段、人工调整和内容校验和。任务运行后不得修改。

### 6. 证据包贯穿全部预测阶段

现有 runners 继续复用，但输入合同扩展为：

```json
{
  "topic": {},
  "ipc_evidence": {
    "series": [],
    "trend_summary": {},
    "fusion_edges": []
  },
  "paper_evidence": {
    "papers": [],
    "direction_summary": {},
    "citations": []
  },
  "material_evidence": [],
  "operator_notes": "",
  "evidence_quality": {}
}
```

- Round 1 分别输出 IPC 推断、论文方向推断、融合结论及引用 ID。
- Round 2 接收各主题的证据摘要和冲突项，不只接收结论文本。
- Round 3 接收全部主题的节点级结论，不能只截取首个瓶颈和突破。
- 分主题路线图同时接收原始证据摘要、Round 1 结论和节点约束。
- 输出中的每个核心 conclusion/milestone 必须包含 `evidence_ids`、`confidence`、`assumptions` 和 `uncertainty_reason`。

大模型负责解释、情景推演和证据融合；统计数据由检索层计算并以只读方式提供。

### 7. 质量门槛优先于兜底生成

默认启动门槛：

- 每个主题至少存在 1 条有效 IPC 时间序列。
- 每个主题至少召回 2 篇论文和 3 个论文证据片段。
- 数据至少覆盖 3 个年份；最新年份和数据截止时间必须可见。

证据不足时用户可填写理由后强制启动，任务和报告必须标记 `evidence_limited=true`。

阶段产物门槛：

- Round 1 对任一主题为空：该主题失败。
- 所有主题 Round 1 均为空：任务直接失败，不运行后续轮次。
- Round 2/3 为空：任务为 `partial_failed`，结果页面明确展示缺失阶段。
- 路线图使用兜底数据时必须标记 `is_fallback=true`，不得与模型生成结果同等展示。
- 图表失败只影响资产状态，不改变预测结论状态。

### 8. API 按资源域拆分

建议路由：

```text
/api/library/datasets
/api/library/imports
/api/library/papers
/api/library/ipc
/api/projects
/api/projects/{id}/materials
/api/projects/{id}/topics
/api/projects/{id}/evidence-packages
/api/projects/{id}/forecast-jobs
/api/forecast/jobs/{id}/results|charts|assets|export
```

文件上传使用 multipart；JSON 文本使用独立 endpoint。导入和预测都是可查询状态任务。现有 `/api/documents`、`/api/topics` 和 `/api/forecast/jobs` 在兼容期转发到默认项目，并返回弃用提示。

### 9. 前端拆分为研究工作流页面

```text
frontend/src/
├── api/
├── types/
├── components/
├── charts/
├── pages/
│   ├── DataLibraryPage
│   ├── ProjectListPage
│   ├── MaterialInputPage
│   ├── TopicCalibrationPage
│   ├── EvidenceReviewPage
│   ├── ForecastRunPage
│   └── ForecastResultPage
└── app/
```

完整交互顺序：

```text
基础数据 → 新建项目 → 输入材料 → 提取主题 → 校准主题
        → 检索证据 → 审阅证据 → 启动预测 → 分析结果
```

结果页新增：

- IPC 年度趋势折线、增长率和中心度变化。
- IPC 融合网络及跨年份 Sankey。
- 论文年度数量、关键词演化和研究方向分布。
- IPC 与论文证据收敛/冲突矩阵。
- 2030/2035/2040 分主题路线图、TRL 和不确定性。
- 点击任一结论查看论文引用、IPC 数据点和原始材料片段。

已有 PNG 资产预览继续保留，结构化 ECharts 用于交互分析。

### 10. 资源目录和 Git 边界

目标目录：

```text
data/seed/                 # 可跟踪的最小演示数据
docs/research/             # 研究草稿与方法文档
var/library/raw/           # 导入原文件
var/library/parsed/        # 解析结果
var/library/index/         # SQLite/全文索引
var/projects/              # 项目附件和快照
var/jobs/                  # 任务中间产物
var/exports/               # 报告与图片
```

`var/`、`logs/`、`frontend/dist/`、`.tools/` 和 `.env` 不进入 Git。历史上已经被跟踪的可再生产物从 Git 索引移除，但不删除本地文件。根目录 `skills/` 先确认是否为项目运行依赖；若无依赖，则移至仓库外工具目录，不在本变更中直接删除。

## Risks / Trade-offs

- **中文 FTS 以 token 为基础，复杂语义召回有限** → 首版结合关键词、IPC 和短语匹配；预留 reranker 接口，后续再评估向量检索。
- **PDF 可能是扫描件或排版复杂** → 标记低文本覆盖率并提示用户提供 OCR 文本；首版不隐式调用 OCR。
- **大文件导入占用磁盘和解析时间** → 设置大小、页数、行数限制，使用 staging 和异步状态，重复文件按 checksum 去重。
- **SQLite 写并发有限** → 使用短事务、WAL 和单写者导入队列；当前本地单用户场景可接受。
- **现有 prompt 和 parser 合同变化面较大** → 通过证据适配器保持旧输入可运行，并逐轮迁移、逐轮增加契约测试。
- **证据门槛可能阻止探索性预测** → 允许有理由的人工覆盖，但显著标记证据受限，不能静默绕过。
- **资源迁移可能误伤用户结果** → 先复制和校验，再切换路径；清理 Git 索引与删除本地文件分离。
- **前端页面拆分可能引入状态同步复杂度** → 项目 ID 作为路由主键，服务端状态为事实来源，避免只依赖组件内存。

## Migration Plan

1. 增加新目录和忽略规则，建立资源清单；不删除任何现有文件。
2. 创建 SQLite schema、迁移版本表和 repository 层。
3. 将现有 `topics.json`、融合对和样例摘要导入 `data/seed/` 对应的种子数据集。
4. 实现基础数据导入、预览和查询 API，再增加前端基础数据页面。
5. 引入项目实体，将现有全局工作台数据迁入一个 `legacy-default` 项目。
6. 实现材料文件解析、主题校准和证据检索；旧 API 暂时转发到默认项目。
7. 扩展预测输入合同和各轮 prompt/parser，增加阶段质量门槛。
8. 增加学术可视化与证据追溯，确认新旧报告兼容。
9. 全量回归并完成数据迁移校验后，从 Git 索引移除历史运行产物。

回滚时保留原始 JSON、旧 API 适配器和旧 CLI 路径；SQLite 数据库与 `var/` 目录可独立移除，不影响原始种子数据。

## Open Questions

- 首版论文中文全文检索是否只要求精确词/短语召回，还是必须加入本地 embedding reranker？
- IPC 表格的实际列名和指标集合是否稳定，是否需要提供可保存的字段映射模板？
- 是否要求从论文正文自动抽取参考文献，还是首版只使用用户导入的 DOI/作者/年份元数据？
- 证据不足的强制启动权限是否对所有本地用户开放，还是需要管理员配置开关？
- 历史 `skills/` 目录是否仍被外部工作流依赖，迁移前需要确认其所有者。
