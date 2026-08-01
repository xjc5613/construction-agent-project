# 交互式技术预测工作台 - 验证检查清单

## API基础结构
- [ ] Checkpoint 1: `src/api/app.py` 可创建 FastAPI 应用实例
- [ ] Checkpoint 2: Pydantic schema 覆盖文档、候选主题、预测任务、任务状态和预测结果
- [ ] Checkpoint 3: 本地 storage 可读写 documents、topics、jobs
- [ ] Checkpoint 4: API模块不影响 `python -m src.main`

## 文档输入
- [ ] Checkpoint 5: `POST /api/documents` 支持中文研究文档提交
- [ ] Checkpoint 6: `GET /api/documents/{document_id}` 可读取文档内容和元数据
- [ ] Checkpoint 7: 空文档或非法内容返回清晰错误
- [ ] Checkpoint 8: 文档保存路径位于工作台专用目录，不污染现有 `data/raw`

## 主题抽取
- [ ] Checkpoint 9: 能识别 `G06F`、`G06N-003`、`E04B-001` 等 IPC 格式
- [ ] Checkpoint 10: 能识别度中心度、中介中心度、融合概率和共现关系
- [ ] Checkpoint 11: 能基于现有 `topics.json` 名称和关键词召回候选主题
- [ ] Checkpoint 12: 每个候选主题至少绑定一条证据片段或标记为需人工确认
- [ ] Checkpoint 13: 主题抽取结果包含 evidence_score
- [ ] Checkpoint 14: LLM校正失败时可降级使用规则抽取结果

## 主题校准
- [ ] Checkpoint 15: `POST /api/topics/extract` 返回候选主题列表
- [ ] Checkpoint 16: `GET /api/topics` 可获取当前候选主题
- [ ] Checkpoint 17: `POST /api/topics` 支持人工新增主题
- [ ] Checkpoint 18: `PATCH /api/topics/{topic_id}` 支持编辑主题字段
- [ ] Checkpoint 19: 支持主题勾选、取消勾选和删除
- [ ] Checkpoint 20: `POST /api/topics/normalize` 输出兼容现有 round1 输入结构

## 预测任务编排
- [ ] Checkpoint 21: `POST /api/forecast/jobs` 可创建预测任务
- [ ] Checkpoint 22: `GET /api/forecast/jobs/{job_id}` 可查询任务状态
- [ ] Checkpoint 23: 任务阶段包含 topic_normalization、round1、round2、round3、per_topic_roadmap、report
- [ ] Checkpoint 24: 可配置自洽性、多Agent、多模型、推理链条和分主题路线图
- [ ] Checkpoint 25: 预测节点固定支持 2030、2035、2040
- [ ] Checkpoint 26: 2025 作为基线阶段保留在路线图数据中
- [ ] Checkpoint 27: 单主题失败不会中断其他主题
- [ ] Checkpoint 28: 任务输出保存到 job 专用目录，不覆盖现有缓存

## 结果接口
- [ ] Checkpoint 29: `GET /api/forecast/jobs/{job_id}/results` 返回完整结构化结果
- [ ] Checkpoint 30: `GET /api/forecast/jobs/{job_id}/charts` 返回 timeline 数据
- [ ] Checkpoint 31: charts 返回 TRL series 数据
- [ ] Checkpoint 32: charts 返回 fusion network 数据
- [ ] Checkpoint 33: charts 返回 uncertainty heatmap 数据
- [ ] Checkpoint 34: 结果中核心结论可追溯到 IPC、融合对、文档证据或人工说明
- [ ] Checkpoint 35: 结果中包含置信度或不确定性摘要

## 学术导出
- [ ] Checkpoint 36: `GET /api/forecast/jobs/{job_id}/export?format=json` 可导出 JSON
- [ ] Checkpoint 37: `GET /api/forecast/jobs/{job_id}/export?format=markdown` 可导出 Markdown
- [ ] Checkpoint 38: Markdown 报告包含摘要、数据来源、方法说明、路线图、融合变化、不确定性、结论和局限性
- [ ] Checkpoint 39: 报告结论与证据链对应清晰

## 前端基础
- [ ] Checkpoint 40: `frontend/` 项目可安装依赖并启动
- [ ] Checkpoint 41: 前端 API client 与后端接口路径一致
- [ ] Checkpoint 42: 主工作台包含文档输入、主题校准、预测配置、任务进度、结果展示区域
- [ ] Checkpoint 43: 页面中文显示正常，长文本可折叠或查看详情

## 前端文档与主题校准
- [ ] Checkpoint 44: 用户可粘贴研究文档并提交
- [ ] Checkpoint 45: 用户可触发主题抽取
- [ ] Checkpoint 46: 候选主题表展示主题名、关键词、IPC、融合对、证据片段和证据强度
- [ ] Checkpoint 47: 用户可新增、编辑、删除和选择主题
- [ ] Checkpoint 48: 人工补充主题可进入预测输入

## 前端任务与结果
- [ ] Checkpoint 49: 用户可创建预测任务
- [ ] Checkpoint 50: 页面可展示每个预测阶段的状态和进度
- [ ] Checkpoint 51: 失败信息可见，并提供重试入口或说明
- [ ] Checkpoint 52: 页面展示 2030/2035/2040 时间轴路线图
- [ ] Checkpoint 53: 页面展示 TRL 演化曲线
- [ ] Checkpoint 54: 页面展示技术融合网络
- [ ] Checkpoint 55: 页面展示不确定性热力图
- [ ] Checkpoint 56: 页面展示证据追溯表和推理链条
- [ ] Checkpoint 57: 页面展示学术结论、方法说明和局限性
- [ ] Checkpoint 58: 用户可导出 JSON 和 Markdown

## 测试与回归
- [ ] Checkpoint 59: 后端新增单元测试通过
- [ ] Checkpoint 60: 文档到报告的 mock 集成测试通过
- [ ] Checkpoint 61: 前端构建或 smoke test 通过
- [ ] Checkpoint 62: 现有测试全部通过
- [ ] Checkpoint 63: README 包含 API 和前端启动说明
- [ ] Checkpoint 64: 默认命令行预测流程无回归
