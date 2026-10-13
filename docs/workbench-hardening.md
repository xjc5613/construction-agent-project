# 工作台生命周期、证据门禁与任务恢复

## 统一状态与证据门禁

- 项目支持 `active`、`archived`；材料支持 `active`、`inactive`；数据集支持
  `active`、`deprecated`，仅无记录、无引用的草稿可物理删除。归档或废弃不会修改
  已冻结的任务快照。
- 后端 readiness v2 服务是流程完整度、当前阶段、项目步骤可见性、推荐动作、证据评分
  和预测启动条件的唯一来源。
  评分由 IPC、年份覆盖、论文、论文片段和非历史项目的三阶段覆盖共同计算；只有全部
  条件通过时才会得到 100 分及 `sufficient=true`。
- 证据不足属于可覆盖条件时，必须显式勾选覆盖并填写可审计理由。未确认主题、待复核
  主题、归档项目等结构性阻断条件不能覆盖。
- 归档、删除、合并、分类、预测启动、取消和重试均先调用 preview，确认界面展示影响后
  再携带短期、一次性、与 payload 绑定的 token 提交。

## 可恢复路由与任务控制

项目主流程使用 `/projects/:projectId/overview|materials|topics-evidence|forecast|results`，
结果详情使用
`/projects/:projectId/jobs/:jobId/results`。复制链接、刷新以及浏览器前进后退都会从后端
恢复项目、readiness、任务进度与结果；任务历史页可恢复结果、取消活动任务或从失败任务
创建带父任务关联的新重试任务。

每个项目同一时刻最多有一个 `queued`、`running` 或 `cancelling` 任务。启动请求使用
幂等键和请求校验和防止双击或网络重试创建重复任务。取消在安全阶段边界生效，已生成的
部分产物会保留；重试创建新任务，不修改父任务。

## 数据迁移、核验与回滚

先对数据库做一致性副本，再在副本上运行协调命令：

```bash
sqlite3 var/library/index/library.sqlite3 ".backup '/tmp/library-copy.sqlite3'"
python3 -m scripts.reconcile_workbench_jobs \
  --database /tmp/library-copy.sqlite3 \
  --jobs-dir data/workbench/jobs \
  --backup-dir /tmp/library-backups
```

命令会再次生成带 UTC 时间戳的备份，导入文件任务；旧任务缺少 `project_id` 时优先关联
`legacy-default`，运行中任务标记为可重试的 `worker_interrupted`，完成或部分完成结果保持
只读。回滚时停止服务，以命令输出的备份替换数据库，并保留 job 目录即可；v4 迁移仅新增
列和索引，不会重写完成结果。当前 schema 版本为 5，V5 仅增加技术有效状态和按技术记录
查询所需索引。

2026-08-02 使用当前本地数据的 SQLite 一致性副本完成核验：`integrity_check=ok`，schema
版本为 5；两个基线为 2025 的历史项目均可读取；3 个 `needs_mapping` 数据集保持原状；旧
任务 `forecast_20260731_175750_eff3b8` 导入为 `legacy-default` 的 `partial_failed` 历史任务，
`artifact_health=ready`，其 `result.json` 通过 JSON 可读性检查。核验仅操作
`/tmp/construction-agent-migration.aju5RX` 下的副本，没有修改生产数据。

## 验证命令

```bash
PYTHONPYCACHEPREFIX=/tmp/construction-agent-pyc python3 -m pytest -q
cd frontend
npm run build
npm run test:e2e
```

Playwright 通过路由级模拟 API 覆盖完整工作流、证据覆盖、重复提交、深链恢复、缺失产物、
危险操作确认、按技术引导导入、输入校验、未保存导航、键盘弹窗，以及 390px/1024px 无文档
级横向溢出。失败时保留截图、视频和 trace；不调用真实模型或付费供应商。
