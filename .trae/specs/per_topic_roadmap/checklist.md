# 分主题技术路线图模块 - 验证检查清单

## Prompt与消息构建
- [x] Checkpoint 1: per_topic_roadmap_system.txt包含清晰的角色设定、任务描述和输出格式要求
- [x] Checkpoint 2: per_topic_roadmap_user.txt模板包含所有必要的占位符（主题名称、瓶颈、突破、融合场景等）
- [x] Checkpoint 3: build_per_topic_roadmap_messages函数能正确构建messages列表，信息完整
- [x] Checkpoint 4: Prompt风格与现有三轮预测保持一致

## 输出解析器
- [x] Checkpoint 5: 能正确解析纯JSON格式的路线图输出
- [x] Checkpoint 6: 能正确解析markdown代码块包裹的JSON
- [x] Checkpoint 7: 能处理带前后缀文本的JSON（提取中间部分）
- [x] Checkpoint 8: 解析结果包含完整字段：topic_name, roadmap(4个阶段), 每个milestone含name/description/key_technologies/trl_level/dependencies/uncertainty_level
- [x] Checkpoint 9: 空输入或格式错误时优雅降级，不抛出异常
- [x] Checkpoint 10: JSON结构符合schema定义，字段类型正确

## 单主题路线图生成
- [x] Checkpoint 11: run_per_topic_roadmap函数能正确调用LLM并解析结果
- [x] Checkpoint 12: 每个主题的路线图至少包含4个时间阶段（2025/2030/2035/2040）
- [x] Checkpoint 13: 每个时间阶段至少包含2条里程碑
- [x] Checkpoint 14: 缓存机制正常（force_rerun=False时读取缓存文件）
- [x] Checkpoint 15: force_rerun=True时忽略缓存重新生成
- [x] Checkpoint 16: 与自洽性验证功能兼容（开启时正常工作）
- [x] Checkpoint 17: 与多Agent辩论功能兼容（开启时正常工作）
- [x] Checkpoint 18: 与多模型集成功能兼容（开启时正常工作）

## 批量处理
- [x] Checkpoint 19: run_all_topics_roadmap能处理所有9个主题
- [x] Checkpoint 20: 单个主题失败时不影响其他主题，继续执行
- [x] Checkpoint 21: 失败的主题有日志记录
- [x] Checkpoint 22: 汇总结果格式正确，包含所有成功的主题
- [x] Checkpoint 23: 汇总结果文件正确保存到指定路径
- [x] Checkpoint 24: 文件名处理正确（中文/特殊字符转义）

## 报告生成 - 时间轴
- [x] Checkpoint 25: 生成的Markdown报告包含Mermaid时间轴
- [x] Checkpoint 26: Mermaid timeline语法正确，可正常渲染
- [x] Checkpoint 27: 时间轴包含所有4个阶段
- [x] Checkpoint 28: 每个阶段的里程碑正确显示在时间轴上

## 报告生成 - 流程图
- [x] Checkpoint 29: 生成的Markdown报告包含Mermaid流程图
- [x] Checkpoint 30: Mermaid flowchart语法正确，可正常渲染
- [x] Checkpoint 31: 流程图体现从2025到2040的技术演进方向
- [x] Checkpoint 32: 流程图中正确体现依赖关系（dependencies字段）
- [x] Checkpoint 33: 流程图节点包含关键信息（里程碑名称、TRL等级）

## 整合报告
- [x] Checkpoint 34: 整合报告包含所有9个主题的路线图
- [x] Checkpoint 35: 整合报告有目录/索引，便于导航
- [x] Checkpoint 36: 整合报告包含统计汇总（总里程碑数、各阶段数量等）
- [x] Checkpoint 37: 每个主题有独立的章节，包含时间轴+流程图+详细表格

## 系统集成
- [x] Checkpoint 38: settings.py中新增ENABLE_PER_TOPIC_ROADMAP配置项
- [x] Checkpoint 39: 配置项可通过环境变量覆盖
- [x] Checkpoint 40: 关闭该功能时，现有三轮预测完全不受影响
- [x] Checkpoint 41: 开启该功能时，主流程正确调用分主题路线图模块
- [x] Checkpoint 42: 提供独立运行的入口脚本
- [x] Checkpoint 43: 最终报告中包含分主题路线图的链接或章节

## 测试与质量
- [x] Checkpoint 44: 所有新增单元测试通过
- [x] Checkpoint 45: 所有现有测试通过（无回归）
- [x] Checkpoint 46: 测试覆盖率合理（核心路径均有测试）
- [x] Checkpoint 47: 代码风格与现有项目一致
- [x] Checkpoint 48: 代码注释清晰，关键算法有说明
