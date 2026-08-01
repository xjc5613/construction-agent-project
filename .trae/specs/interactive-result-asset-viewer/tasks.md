# 结果资产查看器与技术发展详情 - 实施计划

## [x] Task 1: 建立 job 图表资产服务
- **Priority**: high
- **Depends On**: None
- **Description**:
  - 新增 `src/api/asset_service.py`。
  - 复用 `src/report/roadmap_charts.py` 的 `generate_all_charts` 与跨主题比较图函数。
  - 为路线图主题生成稳定、URL-safe 的 `topic_id` 和 `asset_id`。
  - 将 PNG 输出写入 `data/workbench/jobs/<job_id>/assets/`。
  - 建立 `assets.json`，登记图表种类、主题、文件名、MIME、URL 和错误信息。
- **Acceptance Criteria Addressed**: AC-1, AC-2
- **Test Requirements**:
  - `programmatic` TR-1.1: mock 图表生成器可输出三类主题资产。
  - `programmatic` TR-1.2: 图表失败时其余资产仍被索引。
  - `programmatic` TR-1.3: 索引不包含绝对文件路径。

## [x] Task 2: 将资产生成接入预测任务
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - 在 `run_forecast_job` 的 report 阶段生成并保存图表资产。
  - 保存图表资产警告，不覆盖已有 `result.json`、`charts.json`、`report.md`。
  - 在结果结构中增加 `asset_summary`，仅包含计数和状态。
- **Acceptance Criteria Addressed**: AC-1, AC-7
- **Test Requirements**:
  - `programmatic` TR-2.1: 完成任务后存在 `assets.json`。
  - `programmatic` TR-2.2: 部分资产失败不导致预测结果丢失。

## [x] Task 3: 新增结果主题与资产 API
- **Priority**: high
- **Depends On**: Task 2
- **Description**:
  - 实现主题列表、主题详情、资产索引和资产文件 API。
  - 支持主题名、年份、TRL、不确定性、资产种类筛选。
  - 资产文件仅允许通过索引的 `asset_id` 访问，支持下载响应头。
  - 为资产不存在、job 不存在和路径非法增加明确的 404/400 响应。
- **Acceptance Criteria Addressed**: AC-2, AC-3, AC-7
- **Test Requirements**:
  - `programmatic` TR-3.1: 可返回可筛选主题列表。
  - `programmatic` TR-3.2: 主题详情包含阶段、里程碑、证据和资产元数据。
  - `programmatic` TR-3.3: 有效 asset_id 返回 PNG；无效 ID 返回 404。
  - `programmatic` TR-3.4: 路径穿越参数不能读取 job 目录外文件。

## [x] Task 4: 重构结果页为管理台概览
- **Priority**: high
- **Depends On**: Task 3
- **Description**:
  - 将 React 结果区域改为独立的结果管理台页面/组件。
  - 增加顶部任务上下文、侧栏导航、统计卡片、标签页、筛选条和主题数据表。
  - 主题表列包括：主题、2030阶段摘要、2035阶段摘要、2040阶段摘要、终期 TRL、不确定性、图表资产、操作。
  - 不在首页直接加载全尺寸 PNG 图表。
- **Acceptance Criteria Addressed**: AC-4, AC-5
- **Test Requirements**:
  - `programmatic` TR-4.1: 前端可构建。
  - `human-judgement` TR-4.2: 信息层级与示例的管理台密度一致，但使用本项目研究字段。

## [x] Task 5: 实现技术发展详情抽屉
- **Priority**: high
- **Depends On**: Task 3, Task 4
- **Description**:
  - 点击主题表“技术发展”操作后按需获取主题详情。
  - 实现右侧抽屉，显示主题证据与 2025/2030/2035/2040 阶段。
  - 默认突出 2030/2035/2040，2025 使用折叠基线区域。
  - 展示每个里程碑的关键技术、TRL、不确定性和依赖。
- **Acceptance Criteria Addressed**: AC-5, AC-6
- **Test Requirements**:
  - `programmatic` TR-5.1: 点击操作会请求主题详情 API。
  - `human-judgement` TR-5.2: 读者可在一个抽屉中理解技术从基线到2040的发展过程。

## [x] Task 6: 实现图表资产预览与下载
- **Priority**: high
- **Depends On**: Task 3, Task 4
- **Description**:
  - 点击主题表“查看图表”操作后打开预览模态框。
  - 模态框以 Tab 切换综合分析、时间轴、雷达图。
  - 图像加载使用资产 API URL；支持新窗口查看和下载 PNG。
  - 图表资产标签页提供全部资产的可筛选目录。
- **Acceptance Criteria Addressed**: AC-3, AC-4, AC-6
- **Test Requirements**:
  - `programmatic` TR-6.1: 预览加载的是 asset_id URL，而不是本地路径。
  - `programmatic` TR-6.2: 无资产主题显示空状态。
  - `human-judgement` TR-6.3: 用户可在不离开结果页的情况下切换和查看图表。

## [x] Task 7: 测试、文档与回归
- **Priority**: high
- **Depends On**: Task 1-6
- **Description**:
  - 添加资产服务/API 和前端交互测试。
  - 更新 README，说明结果资产生成、浏览和下载方式。
  - 执行 Python 全量测试和前端生产构建。
- **Acceptance Criteria Addressed**: AC-7
- **Test Requirements**:
  - `programmatic` TR-7.1: 新增 API 和资产服务测试通过。
  - `programmatic` TR-7.2: `python3 -m pytest tests/ -q` 通过。
  - `programmatic` TR-7.3: `npm run build` 通过。
