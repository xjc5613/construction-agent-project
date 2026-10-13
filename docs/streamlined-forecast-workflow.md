# 按技术组织的预测工作流

## 页面结构

未进入项目时，侧栏只显示工作台、技术目录、基础数据和预测项目。选择“进入项目”
后，项目工作区按以下顺序展开：

```text
项目概览 -> 研究材料 -> 主题与证据 -> 预测运行 -> 结果与历史
```

项目概览使用后端 readiness v2 显示每一步的完成状态、阻断原因和唯一推荐动作。
直接打开未满足前置条件的路由时，页面会显示原因并引导至当前可执行步骤。旧
`/topics`、`/evidence` 和 `/jobs` 深链仍可恢复到合并后的页面。

## 技术与基础数据

技术目录主界面只维护三级结构和查看数据覆盖。技术描述、关键词和别名位于高级匹配
设置；稳定 ID、跨域关系、引用和变更记录位于高级治理。停用父技术会使全部后代继承
停用状态，但不会改写后代自身状态或历史任务快照。

基础数据先选择技术，再查看论文、IPC 聚合指标、来源文件、导入记录和阶段覆盖。导入
不再要求预先创建数据集：

```text
选择三级技术和数据类型 -> 上传 -> 解析预览 -> 确认阶段拆分 -> 提交 -> 发布
```

系统按记录年份拆分 `2010-2015`、`2016-2020`、`2021-2026`，并生成
`YYYYMMDD.N` 版本。当前 IPC 列表是年度专利量、增长率和中心度等聚合指标，不是逐件
专利文献。

## 证据范围

新证据包只允许使用：

- 项目一级技术范围内的有效三级技术；
- 主题已确认关联的技术；
- `mapped + active + published` 的数据集；
- 至少包含一条有效论文或 IPC 记录的版本。

高级检索参数只能缩小范围，不能选择无关技术的数据集。没有符合条件的数据时返回空
范围和补数提示，不会回退查询全库。预测任务冻结技术路径、目录版本、可用及选中数据集、
查询参数、证据 ID 和范围校验和。

## 迁移与回滚

停止服务并备份数据库：

```bash
sqlite3 var/library/index/library.sqlite3 \
  ".backup '/tmp/library-before-streamlined-workflow.sqlite3'"
```

在副本上执行只读盘点：

```bash
python3 scripts/inventory_workflow_data.py \
  --database /tmp/library-before-streamlined-workflow.sqlite3 \
  --output /tmp/workflow-inventory.json
```

盘点报告列出有效/继承停用技术、数据集记录数、`mapped`、`needs_mapping`、
`needs_split` 状态、项目、证据包、任务和文件目录。非 `mapped` 数据保留原记录和文件，
但不会进入新预测；完成映射或按阶段拆分后才能重新发布。

升级由 `LibraryDatabase` 自动应用增量 schema V5 索引，不删除表、列或业务记录。验证：

```bash
python3 -m pytest -q
./scripts/workbench.sh build
cd frontend && npm run test:e2e
openspec validate streamline-technology-data-forecast-workflow \
  --type change --strict --no-interactive
```

回滚时停止服务，保存升级后新增的导入文件和数据集，再用备份替换
`var/library/index/library.sqlite3`。已有证据包、任务快照和结果不需要重算。
