# 第四章证据包与第五章多智能体研判

本流程以第四章已经形成的分阶段识别和动态演化结论为证据边界。第五章不重新发现主题，也不把 IPC 节点指标直接改写成主题增长率、工程性能或成熟度结论。

## 证据包边界

证据包使用 `evolution-evidence-packet-v1`，必须完整保留 `T01`–`T09`；`C01`–`C06` 仅作为可选候选，不自动合并或晋升为主题。主要字段为：

- 主题名称、定义、关键词、典型技术；
- Q（主题事实）、N（网络观察）、H（语义关系）、M（方法指标），以及可选工程来源和经人工审核的派生模型证据；
- 阶段、结构化数值、单位、来源位置、适用边界、`supports` 与 `does_not_support`；
- 可选的 IPC—专利—主题映射附件和代表专利。

`null` 表示未知或尚未核实，不能替换为 0。0 只有在来源明确记录数值为零时才有效。来源位置可指第四章表、图、段落、文件或已有确定性产物。

映射状态分别为 `supplied_verified`、`supplied_unverified`、`reported_but_not_supplied` 和 `unavailable`。例如论文报告已映射 926 件专利、但未提供逐行表时，应使用 `reported_but_not_supplied`；不能因此声称某 IPC 已逐条归属于某主题。

T03 机器人示例可记录 B25J-011 在三阶段的度中心度 0.0405、0.0832、0.1462，并明确“这是 IPC 节点的结构轨迹，不是机器人集群协同主题的增长率”。T08 增材制造示例应分别保留 B33Y-070 各指标的方向；指标方向不一致时不得压缩为单一的“全面增长”。

证据包按 `packet_id + version` 追加，经过 `draft → reviewed → frozen`。冻结后不覆盖；任何补充都创建新版本，并通过 checksum 和 diff 追踪。

## 三种任务模式

- `thesis_evolution_forecast`：只接受已审核冻结的第四章证据包，输出可追溯的发展命题、审查、裁决和路线图。
- `ipc_fusion_discovery`：保留现有确定性融合概率和候选发现，不直接改变论文对象。
- `legacy_read_only`：读取旧版 0–100 confidence 和 TRL 结果，并明确标注为旧语义。

发现模式的结果只有经人工审核后，才能以 `derived_model_evidence` 导入证据包新版本。它仍需映射到已有 T/C 对象，并保留模型、审核人和局限，不能创建新主题。

## 五类智能体责任

演化分析智能体只读冻结数值与缺失项；命题生成智能体将结论拆成原子命题；反向审查智能体检查替代解释、时间泄漏、因果与范围漂移；工程审查智能体检查任务、接口、环境、安全、可靠性和验证条件；裁决智能体依据证据作 `accept/revise/downgrade/defer` 决策。局部修订器只修改被指出的命题字段，不改变对象、证据包或历史版本。

反向审查与工程审查相互独立并行。修订后的命题必须重新进行确定性校验和双审查；达到修订上限时记为 `revision_exhausted`，不会阻塞其他命题。

## 三个人工审核门

1. 证据审核：确认第四章证据边界和缺失说明；
2. 命题审核：检查命题、引用、双审查和裁决，可产生具有理由的新命题版本；
3. 发布审核：检查路线图、跨主题关系、未解决缺口和覆盖率。

## 四类不同量

`support_level` 表示论断被证据支持的方式；确定性融合概率属于发现模型；评审一致性描述审查过程；TRL 是采用指定量表并有成熟度证据时才可填写的工程等级。这四类量不得互相替代。

## 迁移与接口

先执行只读盘点：

```bash
python scripts/migrate_evolution_evidence.py --db var/library.sqlite3
```

审核 JSON 后再追加导入：

```bash
python scripts/migrate_evolution_evidence.py \
  --db var/library.sqlite3 --input packet.json --project-id PROJECT_ID \
  --apply --reviewed-confirmation --report migration-report.json
```

HTTP 入口位于 `/api/thesis`，提供证据包创建、审阅、冻结、版本 diff、经审发现导入、任务启动、三个审核门、恢复/取消、命题谱系、完整结果和研究导出。
