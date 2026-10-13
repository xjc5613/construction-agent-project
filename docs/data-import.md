# 基础数据导入与恢复

## 导入模板

可从以下模板开始整理数据：

- `docs/templates/ipc_metrics.csv`
- `docs/templates/ipc_fusions.csv`
- `docs/templates/papers.csv`

基础数据页面先选择技术范围并直接查看论文、IPC 聚合指标、来源文件、导入记录和阶段
覆盖。导入时必须选择三级技术和数据类型；数据类型仅包含 IPC、论文、综合数据。

IPC 趋势必填 `ipc_code`、`year`，其余指标可为空。IPC 融合必填
`ipc1`、`ipc2`、`probability`，其中概率范围为 0 到 1。论文元数据必填
`title`，建议同时提供作者、年份、DOI、关键词和摘要。

导入流程为“选择三级技术和类型 -> 上传并预览 -> 检查字段映射、错误行和阶段拆分 ->
确认提交 -> 发布”。系统根据年份自动拆分 `2010-2015`、`2016-2020`、
`2021-2026` 并生成 `YYYYMMDD.N` 版本，不需要先手工创建数据集。

PDF、DOCX、TXT 和 Markdown 会作为论文文档解析。扫描版 PDF 不执行隐式
OCR；文本覆盖率过低时会标记为待复核，空文本不会写入论文证据。

综合数据允许连续上传多个组成文件，但发布前必须至少提交一个 IPC 组成和一个
论文组成。表格或论文年份超出所选阶段时会在预览中报错。

## 备份

停止工作台后备份以下目录：

```text
var/library/
var/projects/
var/jobs/
var/exports/
```

其中 `var/library/index/library.sqlite3` 是结构化索引，`var/library/raw/`
保存导入原文件。两者应放在同一备份批次中。

## 恢复

1. 停止前后端服务。
2. 将备份目录恢复到原路径。
3. 执行 `python3 scripts/seed_library.py --include-legacy-project`，该命令是幂等的。
4. 执行 `./scripts/workbench.sh check`。
5. 启动服务并检查 `/api/health`、`/api/library/datasets` 和 `/api/projects`。

## 故障排查

- 重复文件：系统按 SHA-256 校验和拒绝重复写入，改用新文件内容或复用现有版本。
- 表格无有效行：检查年份范围、IPC 字段和概率范围，并在导入预览中查看行号。
- 论文无法检索：确认数据集状态为“已发布”，且文档解析结果包含正文。
- SQLite 被锁定：确认没有重复启动多个后端；数据库使用 WAL 和 30 秒忙等待。
- 证据不足：每个主题默认至少需要 IPC 覆盖 3 年、2 篇论文和 3 个论文片段。
- 数据已导入但项目无法检索：检查数据集是否为 `mapped + active + published`，并确认
  至少存在一条有效记录；`needs_mapping` 和 `needs_split` 只用于治理查看。
- “IPC 指标列表”不是逐件专利库：当前结构保存 IPC 分类号、年份、专利量、增长率和
  中心度等聚合记录。

完整的项目流程和范围隔离规则见
[`streamlined-forecast-workflow.md`](streamlined-forecast-workflow.md)。
