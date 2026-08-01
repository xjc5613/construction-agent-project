# 结果资产查看器与技术发展详情 - 技术设计

## Design Principles
- **资产与数据分离**：预测数据保存在 `result.json`，图片保存在 job 资产目录，API 通过资产 ID 关联二者。
- **前端按需展示**：结果首页只加载统计、主题列表和缩略信息；用户点击后才请求图片二进制和完整路线详情。
- **后端不渲染页面**：FastAPI 只生成资产、提供元数据和文件响应；所有布局、预览、筛选和详情交互在 React 前端完成。
- **管理台信息层级**：参考示例图的“侧栏导航 → 页面标题/说明 → 统计卡片 → 标签页 → 筛选条 → 数据表”组织方式，使用本项目的学术分析字段。

## Architecture
```text
预测任务完成
    │
    ├── 结构化结果
    │   ├── result.json
    │   └── charts.json
    │
    ├── 报告图表生成器
    │   └── generate_all_charts(roadmap, job/assets/<topic_id>/)
    │
    └── 资产索引
        └── assets.json
                 │
                 ▼
FastAPI assets API ──────── React 结果管理台
       │                            │
       ├── 主题列表/详情              ├── 总览卡片
       ├── 资产元数据                 ├── 筛选/标签页
       └── asset_id 文件流            ├── 详情抽屉
                                    └── 图表预览模态框
```

## Job Storage Layout
```text
data/workbench/jobs/<job_id>/
├── result.json
├── charts.json
├── assets.json
├── report.md
└── assets/
    ├── all-topics-comparison.png
    ├── topic_<stable_id>/
    │   ├── combined.png
    │   ├── timeline.png
    │   └── radar.png
    └── ...
```

`assets.json` 是唯一允许映射真实文件路径的索引文件。响应中不返回绝对路径。

## Asset Index Schema
```json
{
  "job_id": "forecast_20260724_001",
  "generated_at": "2026-07-24T10:00:00Z",
  "assets": [
    {
      "asset_id": "asset_7d2f_combined",
      "topic_id": "topic_assembly",
      "topic_name": "装配式建筑技术",
      "kind": "combined",
      "title": "综合分析图",
      "media_type": "image/png",
      "filename": "combined.png",
      "url": "/api/forecast/jobs/forecast_20260724_001/assets/asset_7d2f_combined",
      "download_url": "/api/forecast/jobs/forecast_20260724_001/assets/asset_7d2f_combined?download=true",
      "width": 6600,
      "height": 4800
    }
  ]
}
```

## API Design

### `GET /api/forecast/jobs/{job_id}/topics`
返回结果页主题列表，不返回图片二进制。

Query parameters:
- `q`: 主题名或关键技术搜索。
- `year`: `2030`、`2035`、`2040`。
- `uncertainty`: `low`、`medium`、`high`。
- `min_trl`: 最低 TRL。

Response:
```json
{
  "items": [
    {
      "topic_id": "topic_assembly",
      "topic_name": "装配式建筑技术",
      "status": "completed",
      "milestone_count": 12,
      "terminal_trl": 9,
      "dominant_uncertainty": "medium",
      "asset_count": 3,
      "available_years": ["2030", "2035", "2040"]
    }
  ],
  "total": 1
}
```

### `GET /api/forecast/jobs/{job_id}/topics/{topic_id}`
返回一个主题的路线详情、证据和相关资产元数据，不返回图片内容。

```json
{
  "topic_id": "topic_assembly",
  "topic_name": "装配式建筑技术",
  "evidence": [],
  "stages": {
    "2025": {},
    "2030": {},
    "2035": {},
    "2040": {}
  },
  "assets": []
}
```

### `GET /api/forecast/jobs/{job_id}/assets`
返回全部资产索引，可按 `topic_id`、`kind` 筛选。

### `GET /api/forecast/jobs/{job_id}/assets/{asset_id}`
通过登记资产 ID 返回 `FileResponse`。仅允许访问 `assets.json` 中登记的文件；禁止把前端参数当作本地路径使用。

## Backend Changes
### Asset Service
新增 `src/api/asset_service.py`：
- 为路线图主题生成稳定的 URL-safe `topic_id`。
- 调用现有 `generate_all_charts`，但将输出目录设置为 job 的 `assets/`。
- 对图表输出做元数据登记（名称、主题、种类、MIME、尺寸、URL）。
- 捕获单图生成异常，记录 `failed_assets`，不影响其他主题和结果 API。
- 生成所有主题对比图并登记为 `topic_id=null` 的全局资产。

### Forecast Service
在 `run_forecast_job` 的 report 阶段：
1. 保存 `result.json` 和现有 ECharts `charts.json`。
2. 调用资产服务生成 job 资产。
3. 保存 `assets.json`。
4. 即使图片资产部分失败，也保存预测结果并将 job 状态标记为 `partial_failed` 或携带资产警告。

### API Safety
- 资产文件的 ID 从索引中查找。
- 使用 `Path.resolve()` 验证目标文件仍位于 job 的 `assets/` 下。
- 不返回真实机器路径、异常堆栈或任意文件名查询能力。

## Frontend Design
### Layout
采用科研管理台风格，而不是报告长页：

```text
┌──────────────── 顶栏：项目、任务状态、导出 ────────────────┐
├───────┬───────────────────────────────────────────────────┤
│侧栏   │ 结果总览                                              │
│概览   │ [主题数] [图表资产] [平均置信度] [高不确定主题]         │
│主题库 │ ─ 标签：技术主题 / 图表资产 / 方法与结论 ─             │
│报告   │ 搜索 | 年份 | TRL | 不确定性                [导出]    │
│       │ ┌────────────────────主题数据表───────────────────┐ │
│       │ │主题 │2030 │2035 │2040 │TRL │资产 │操作           │ │
│       │ └───────────────────────────────────────────────┘ │
└───────┴───────────────────────────────────────────────────┘
```

### Interaction
- 点击主题表的“技术发展”按钮：打开右侧详情抽屉。
  - 显示主题摘要、证据、四阶段时间线。
  - 默认突出 2030/2035/2040，2025 作为可折叠基线。
  - 每个里程碑显示 TRL、不确定性、依赖、关键技术。
- 点击“查看图表”：打开资产预览模态框。
  - 先请求资产清单，再加载当前选中图片。
  - 在模态框中以 Tab 切换综合图、时间轴、雷达图。
  - 支持“在新窗口打开”和“下载 PNG”。
- 点击“图表资产”标签：展示资产库，允许按主题和图表类型筛选。
- 结果首页不直接渲染全尺寸 PNG，仅显示数量、状态和小型文本摘要。

### Visual Direction
- 白色/浅灰管理台底色、紫蓝主色、克制的状态色，与示例的高密度信息布局对齐。
- 保留本项目中文科研语义：卡片指标、表格字段、步骤状态和证据标签。
- 使用紧凑左侧导航、顶部任务上下文、分组统计卡片、标签页与表格，不复刻示例的产品名、Logo 或业务分类。

## Compatibility
- `/results`、`/charts`、`/export` 保持原有返回结构。
- ECharts 数据图表可继续保留为“交互分析”入口。
- 若没有可用的 PNG 资产，前端应显示空状态并仍允许查看技术发展详情。

## Testing Strategy
- 单元测试：资产索引、稳定 ID、路径校验、筛选、单图失败降级。
- API 测试：主题列表、主题详情、资产索引、有效/无效 asset_id、下载响应头。
- 集成测试：mock 路线图生成 + mock 图表函数，验证 job 产物目录。
- 前端测试：列表筛选、点击详情抽屉、点击图表预览、资产 Tab 切换、空资产状态。
- 构建验证：`npm run build` 和现有 Python 全量测试。
