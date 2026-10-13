# 研究契约 v3 输入模板

## 规范专利与 IPC 归属

每行至少包含 `publication_number`、`application_year`、`ipc_codes`。`ipc_codes` 可用分号分隔多个原始 IPC；推荐同时提供 `title`、`abstract`、`applicant_type`、`legal_status`、`ipc_edition`。系统保留原始码并生成主组级规范码。

## 降级年度边

每行包含 `year`、`ipc1`、`ipc2`、`cooccurrence_count`，并应包含 `total_patent_count`、两端出现数、归一化公式与分母说明。此格式必须人工复核，证据等级低于规范专利归属。

## 论文

至少包含 `title`、`publication_date` 或 `year`、`paper_type`、`source_database`；推荐包含作者、关键词、摘要、引用数和引用观察日。类型限定为期刊论文、会议论文、学位论文、综述、书籍章节、报告及显式待复核的 `other`。

## IPC 映射与时间覆盖

映射表包含 `ipc_code_raw`、`ipc_code_normalized`、`analysis_level`、源/目标版本、规则版本、状态和理由。覆盖表按数据集、来源类型和年份提供观测截止、预期数、观测数、完整性与研究者备注。部分 2025 必须填写截止日。
