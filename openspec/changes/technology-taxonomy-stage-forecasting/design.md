## Context

当前 SQLite 数据层把数据集名称、项目名称和项目主题名称作为独立自由文本保存：

- `datasets.kind` 使用 `ipc_metrics`、`ipc_fusions`、`papers`、`mixed`，没有技术节点和历史阶段。
- `projects` 没有技术范围、目标年份或基线字段。
- `project_topics` 是一次预测中的候选主题，不适合作为长期技术分类。
- 预测服务固定以2025为基线并要求2030、2035、2040三个节点。
- IPC与论文可以检索，但尚未形成跨 `2010-2015`、`2016-2020`、`2021-2026` 的统一演化特征。

本变更跨越数据库、导入、检索、项目、主题、预测内核和前端，且需要保证已完成任务的快照不变。系统仍定位为 SQLite 本地研究工作台，不引入外部数据库、图数据库或分布式任务系统。

## Goals / Non-Goals

**Goals:**

- 建立稳定、可维护、可审计的三级技术主数据。
- 让数据集、项目和项目主题通过稳定 ID 关联技术目录。
- 将基础数据统一约束为三种对外类型和三个历史阶段。
- 支持独立综合数据集内的多文件、双源证据组成。
- 用确定性算法计算跨阶段规律，并将其冻结为可引用证据。
- 将新项目基线统一为2026，按目标年份派生累计预测节点。
- 保持旧数据、旧项目和旧任务可读取，迁移过程中不删除用户原始文件。

**Non-Goals:**

- 不把项目候选主题自动提升为技术目录节点。
- 不允许技术节点拥有多个树形父节点；跨域关系通过独立关联表达。
- 不建设通用无限层级分类平台，首版最多三级。
- 不让大模型计算阶段统计量或修改原始数据。
- 不重新计算或改写历史预测任务。
- 不在首版引入在线技术分类标准同步或多人权限审批。

## Decisions

### 1. 技术目录使用邻接表和稳定 ID

新增：

```text
technology_nodes
├── node_id, parent_id, level, name, slug
├── description, keywords_json, aliases_json
├── status, sort_order, taxonomy_version
└── created_at, updated_at

technology_relations
├── relation_id, source_node_id, target_node_id, relation_type
└── created_at

technology_change_logs
├── change_id, node_id, action, before_json, after_json
└── operator, created_at
```

使用 SQLite 递归 CTE 查询后代和路径。数据库与服务层共同校验 `level IN (1,2,3)`、父子层级相差1、无循环、同级名称唯一。技术移动只修改 `parent_id`，`node_id` 永不变化。

未选择 closure table，因为目录规模小且最大深度固定；维护额外闭包表会增加移动节点时的事务复杂度。

### 2. 单一主父节点加跨域关联

技术树负责唯一主归属，`technology_relations` 表达 `related`、`depends_on`、`converges_with` 等关系。数字孪生、大模型、智慧工地等跨域技术不在树中复制。

预置主归属：

| 二级领域 | 三级技术 |
|---|---|
| 工程软件 | 生成式设计、工程分析、数字化设计、工程仿真模拟、参数化设计、大模型、智能设计、BIM |
| 工程物联网 | 智慧工地、施工监测、数字孪生 |
| 构件智能生产 | 3D打印、装配式建筑 |
| 智能施工机械 | 智能施工、架桥机、塔吊、盾构机、机器人 |
| 工程大数据与互联网平台 | 大数据、区块链 |

种子记录是可维护初始目录，不是永久白名单。

### 3. 引用保护通过归档而非级联删除

删除前查询数据集、项目、主题关联、证据包和任务快照引用。存在任何引用时只允许 `status='archived'`。历史任务在自身快照中保存节点 ID、名称、路径和目录版本，不依赖当前树恢复显示。

### 4. 数据集保存对外类型、技术、阶段和版本

重建 `datasets` 约束，核心字段为：

```text
dataset_id
kind                 # ipc | paper | integrated
technology_node_id   # 必须是 level=3
period_code          # 2010_2015 | 2016_2020 | 2021_2026
version
status
migration_status
```

业务唯一键：

```text
UNIQUE(technology_node_id, period_code, kind, version)
```

显示名称由技术、阶段、类型和版本派生，不作为事实字段。现有 `ipc_metrics`、`ipc_fusions`、`papers` 表继续保存结构化内容，导入任务增加内部 `component_kind`：

```text
ipc_metrics | ipc_fusions | papers | analysis_document
```

这样前端只暴露三种数据类型，同时保留现有解析器和表结构。

### 5. 综合数据是独立多文件容器

沿用 `source_files.dataset_id` 的一对多关系，并增加 `content_role` 和解析摘要。综合数据可以多次上传组成文件：

```text
IPC 指标表
IPC 融合表
论文元数据表
论文 PDF/DOCX/TXT/Markdown
综合分析报告
```

发布检查至少存在一个成功提交的 IPC 组成和一个成功提交的论文组成。分析报告可选。不同文件仍按校验和去重并分别显示错误。

没有选择“单一混合文件专用格式”，因为它会把表格映射、文档解析和错误反馈耦合到一个不可复用解析器。

### 6. 历史阶段是证据口径，版本是数据修订

固定阶段在后端常量和数据库 CHECK 中双重约束：

```text
2010_2015: [2010, 2015]
2016_2020: [2016, 2020]
2021_2026: [2021, 2026]
```

结构化记录提交前逐行检查年份。文档论文必须解析或人工填写年份。阶段和版本不得合并为同一字段：阶段表达研究时间，版本表达数据修订。

### 7. 项目保存一级范围和最终目标

`projects` 增加：

```text
technology_node_id   # level=1
baseline_year        # 新项目固定 2026
target_year          # 2030 | 2035 | 2040
scope_version
legacy_mode
```

默认名称为 `<一级技术>-<目标年份>技术预测`，描述或后缀不改变范围。项目创建时保存目录版本；任务启动时查询该一级节点的有效三级后代并冻结完整范围。

派生函数为唯一节点事实来源：

```python
derive_forecast_nodes(2030) -> [2030]
derive_forecast_nodes(2035) -> [2030, 2035]
derive_forecast_nodes(2040) -> [2030, 2035, 2040]
```

前后端、Prompt、Parser、图表和报告均调用或消费该合同，不各自硬编码。

### 8. 项目主题和技术节点使用多对多关联

新增：

```text
project_topic_technologies
├── topic_id, technology_node_id
├── is_primary, relevance, source
└── UNIQUE(topic_id, technology_node_id)
```

主题抽取可以生成融合方向，但确认前必须至少关联一个三级技术且恰有一个主技术。合并主题时合并去重技术关联。编辑技术目录不修改已冻结任务中的主题关联。

### 9. 已分析材料保留类型和证据来源

`project_materials` 增加：

```text
analysis_kind   # ipc_analysis | paper_analysis | integrated_analysis
review_status
```

抽取服务按以下顺序工作：

1. 解析材料中的 IPC、年份、阶段、指标、关键词、方向和融合关系。
2. 根据项目一级范围和材料信号召回三级技术。
3. 加载相关技术三个阶段的最新已发布证据和阶段分析。
4. 规则生成候选主题和技术关联。
5. 可选 LLM 只归纳名称、描述和歧义，不得创建技术节点或统计值。
6. 保存材料片段、技术节点、阶段规律和数据版本。

### 10. 阶段分析持久化为可复现证据

新增：

```text
stage_analysis_runs
├── run_id, technology_node_id, input_checksum
├── algorithm_version, parameters_json, status
└── created_at

stage_analysis_items
├── analysis_id, run_id, direction_key, relation
├── stages_json, metrics_json, evidence_ids_json
├── confidence, limitations_json
└── created_at
```

确定性计算包括：

- IPC：原始量、年均量、CAGR、斜率、中心度变化、变化点、融合边强度变化。
- 论文：原始量、年均量、关键词新增/持续/消退、方向分布、代表论文。
- 双通道：收敛、互补、冲突、证据不足。

不同长度阶段比较必须使用年均值或明确的每年指标，同时保留总量。分析输入 checksum 包含数据集版本、记录 ID 和参数；相同输入复用结果。

### 11. 预测快照扩展而不替换现有证据快照

新任务的 `evidence_snapshot.json` 增加：

```json
{
  "taxonomy": {},
  "baseline_year": 2026,
  "target_year": 2040,
  "forecast_nodes": [2030, 2035, 2040],
  "historical_periods": ["2010_2015", "2016_2020", "2021_2026"],
  "stage_analysis": []
}
```

现有 IPC、论文、材料和人工调整继续保留。质量门槛按项目实际节点验证，2030项目不因缺少2035/2040而失败。

### 12. 前端增加技术管理并收紧选择控件

侧栏增加“技术管理”。页面采用参考图的树与详情布局：

```text
技术目录树与搜索 | 节点详情、下级节点、跨域关联
                 | 数据集/项目引用、变更记录
```

项目页面使用一级技术下拉框和目标年份单选。基础数据页面使用三级技术、数据类型、历史阶段和版本控件。主题校准页面增加技术关联选择器。结果页面按任务节点动态渲染，不展示空年份列。

### 13. API 按资源边界扩展

新增或调整：

```text
GET/POST /api/technologies
GET/PATCH /api/technologies/{id}
POST /api/technologies/{id}/move|archive|restore
GET /api/technologies/{id}/references|changes
POST/DELETE /api/technology-relations

POST /api/library/datasets
POST /api/library/datasets/{id}/files
GET /api/library/coverage

POST /api/projects
GET /api/projects/{id}/technology-scope
PUT /api/projects/{id}/topics/{topic_id}/technologies
POST /api/projects/{id}/stage-analysis
```

响应统一返回稳定 ID 和可读路径。服务端不信任前端提交的层级、阶段边界或派生节点。

## Risks / Trade-offs

- **旧数据无法可靠映射到单一技术或阶段** → 保留原记录和文件，使用 `migration_status='needs_mapping'`，提供校准界面，不自动猜测。
- **三级技术存在跨域属性** → 树只表达主归属，跨域关系单独保存，避免多父树导致路径和权限语义不稳定。
- **综合数据多文件可能出现部分成功** → 文件级 staging 与状态独立，数据集只有满足双源门槛后才能发布。
- **2026基线与旧2025任务并存** → 所有读取以任务快照为准，只有新项目使用2026，历史任务不迁算。
- **动态节点改动现有 Parser 假设** → 先引入统一节点派生函数和参数化契约测试，再逐轮替换硬编码。
- **阶段总量受阶段长度影响** → 强制计算年均和每年增长指标，报告同时展示总量与标准化结果。
- **目录编辑可能影响正在配置的项目** → 项目保存目录版本，任务启动冻结范围；目录变化必须显式刷新项目范围。
- **阶段分析增加计算和存储成本** → 通过输入 checksum 和算法版本缓存，SQLite 当前规模足够。

## Migration Plan

1. 备份 SQLite、`var/library/raw`、`var/projects` 和 `var/jobs`，记录迁移前 schema 版本。
2. 创建技术节点、关系、审计、主题技术关联和阶段分析表，导入预置技术树。
3. 为 `datasets`、`projects`、`project_materials` 增加可空的新字段，先保持旧 API 可读。
4. 运行 dry-run 映射：根据现有主题名、关键词、IPC、文件年份和论文年份生成技术与阶段建议。
5. 对可确定记录创建映射或按阶段拆分派生数据集；不确定记录标记待校准，原记录和文件保持不变。
6. 上线技术管理、基础数据新建和项目新建 API；禁止新记录继续使用自由文本技术名称。
7. 增加主题技术关联和阶段分析，验证三个阶段输入及2026截止。
8. 参数化预测节点、Prompt、Parser、图表和报告，旧任务继续按旧快照读取。
9. 完成前端页面切换、端到端测试和迁移报告后，将旧创建接口标记弃用。

回滚时恢复数据库备份或回退 schema 读路径；新增表和字段不作为删除旧数据的前提。迁移脚本不得删除旧数据集、项目、任务或上传文件。

## Open Questions

- 现有内置九主题到三级技术的初始映射需要在实施时输出校准清单；融合主题应映射多个技术而不是新增目录节点。
- 三级技术跨域关系的首批种子边可依据研究文档生成建议，但必须在发布前人工确认。
