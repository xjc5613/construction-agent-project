# v3 运行、迁移与恢复

## 模型与提示词

本地使用 OpenAI-compatible 提供方；密钥只通过环境变量传给底层客户端，不进入任务状态、事件或清单。每个任务冻结 provider、模型名、温度、最大 token、依赖版本和模型清单。五个 Agent 角色的 system/user 模板位于 `config/prompt_templates`，运行时记录版本与 SHA-256。

图任务在 SQLite 中保存线程、逐节点事件和校验和检查点。`cancel` 只在节点边界生效；`resume` 从最后完整检查点继续；`abandon` 保留历史但终止推进。若检查点校验失败，必须从冻结输入创建新任务，不能跳过校验。

## 迁移

1. 备份数据库与 `var/jobs`、`var/exports`。
2. 运行 `python scripts/migrate_research_v3.py --database PATH`，只生成 dry-run 分类。
3. 逐项复核 `mapped`、`needs_patent_ipc_reconstruction`、`reduced_edge_only`、`needs_period_split` 和 `quarantined_legacy`；不得把后四类直接升级。
4. 只对已书面确认的 ID 使用 `--apply --confirm-reviewed --dataset-id ... --project-id ...`。脚本在修改前创建带 UTC 时间的数据库副本。
5. 运行 `python scripts/migrate_research_v3.py --database PATH --verify`，再执行数据库测试和样例端到端流程。校验同时检查 SQLite 完整性和既有导出路径。旧项目、旧文件和旧结果继续保留并以 legacy 只读标签呈现。

回滚时停止服务，执行 `python scripts/migrate_research_v3.py --restore-from BACKUP --restored-database NEW_PATH`，先用新路径启动只读验证；确认记录数、旧导出和校验和后再切换配置。命令拒绝覆盖已有数据库。

## 影子运行与故障排查

`python scripts/shadow_compare_workflows.py LEGACY_MANIFEST V3_MANIFEST` 输出字段级差异，并明确 `scientific_equivalence_asserted=false`。影子比较用于发现输入和编排差异，不证明两套方法科学等价。

启动诊断会报告 LangChain/LangGraph 版本。结构化输出失败时查看节点事件中的校验错误；达到重试上限后任务显式失败。无校准概率、证据 ID 越界、2026 基线、旧时期码、发布门未通过或未经人工评审均会被拒绝。
