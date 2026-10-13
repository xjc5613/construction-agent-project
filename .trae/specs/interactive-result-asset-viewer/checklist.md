# 结果资产查看器与技术发展详情 - 验证检查清单

## 后端资产
- [ ] Checkpoint 1: 每个 job 的资产文件位于 `data/workbench/jobs/<job_id>/assets/`
- [ ] Checkpoint 2: `assets.json` 为每张 PNG 登记 asset_id、主题、种类、MIME 和 API URL
- [ ] Checkpoint 3: 资产索引不暴露绝对路径
- [ ] Checkpoint 4: 单张图生成失败时其余图表仍可用
- [ ] Checkpoint 5: 全主题综合图作为全局资产登记

## API
- [ ] Checkpoint 6: 主题列表支持名称、年份、TRL、不确定性筛选
- [ ] Checkpoint 7: 主题详情返回阶段、里程碑、证据和相关资产
- [ ] Checkpoint 8: 资产索引支持 topic_id 和 kind 筛选
- [ ] Checkpoint 9: asset_id API 返回正确图片 MIME 和下载响应
- [ ] Checkpoint 10: 无效 asset_id 返回 404
- [ ] Checkpoint 11: 路径穿越无法读取任务资产目录以外的文件
- [ ] Checkpoint 12: 现有 results/charts/export API 未破坏

## 前端结果管理台
- [ ] Checkpoint 13: 结果首页具备顶部任务上下文、统计卡片、标签页和主题表
- [ ] Checkpoint 14: 首页不直接渲染全尺寸 PNG
- [ ] Checkpoint 15: 主题表显示 2030、2035、2040、终期TRL、不确定性和资产数
- [ ] Checkpoint 16: 支持主题名、年份、TRL、不确定性筛选
- [ ] Checkpoint 17: 点击“技术发展”打开主题详情抽屉
- [ ] Checkpoint 18: 详情抽屉清晰展示 2025 基线与 2030/2035/2040 阶段
- [ ] Checkpoint 19: 点击“查看图表”打开资产预览模态框
- [ ] Checkpoint 20: 预览支持综合图、时间轴和雷达图切换
- [ ] Checkpoint 21: 支持下载单个 PNG
- [ ] Checkpoint 22: 无资产时展示空状态而不报错

## 质量
- [ ] Checkpoint 23: 资产服务和 API 测试通过
- [ ] Checkpoint 24: Python 全量测试通过
- [ ] Checkpoint 25: 前端生产构建通过
- [ ] Checkpoint 26: README 说明资产浏览和下载方式
