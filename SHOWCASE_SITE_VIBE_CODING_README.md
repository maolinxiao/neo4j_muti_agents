# 展示网站 Vibe Coding 执行计划

本文档用于指导“药食同源多智能体研发协同平台”展示网站的迭代实现。目标是用 vibe coding 的方式，在现有 Vue 3 + Vite + Element Plus 前端工程内，逐步搭建一个视觉优美、动效自然、可带 3D 效果的公开展示网站，同时保留现有工作台的后台效率和业务稳定性。

## 1. 项目目标

为当前系统新增一个公开展示网站，用于说明平台价值、核心能力、知识图谱底座、多智能体研发流程和企业/个人端应用场景。

展示网站应具备：

- 强首屏识别度：用户进入后立即理解这是“药食同源多智能体研发协同平台”。
- 精致视觉风格：具备科技感、药食同源行业感、知识图谱感，但不过度花哨。
- 3D 或准 3D 体验：优先构建 3D 知识图谱首屏，也允许在低性能设备降级为视频或静态背景。
- 清晰业务叙事：能讲清楚知识问答、体质辨识、研发协同、合规审查、方剂替代等核心能力。
- 与现有系统兼容：不破坏登录页、工作台、知识问答、研发协同、管理后台等已有功能。

## 2. 推荐技术路线

在现有 `frontend/` 工程内实现，不另起独立前端项目。

推荐依赖：

```powershell
cd frontend
npm install three @tresjs/core @tresjs/cientos @vueuse/motion
```

可选增强依赖：

```powershell
cd frontend
npm install gsap
```

技术选择说明：

- `three`：3D 渲染基础库。
- `@tresjs/core`：Vue 组件式 Three.js 封装，适合当前 Vue 3 工程。
- `@tresjs/cientos`：TresJS 辅助组件，用于相机、光照、浮动、文本、控制器等。
- `@vueuse/motion`：页面入场、滚动出现、按钮和卡片微交互。
- `gsap`：仅在需要高级滚动叙事或 3D 相机时间轴时引入。
- 现有 `frontend/remotion/`：继续作为登录背景、展示站视频 fallback 或视觉资产生成工具。

## 3. 路由设计

建议将公开展示站与业务工作台分离。

目标路由：

```text
/                 公开展示网站首页
/login            登录页
/app              工作台首页
/app/chat         知识问答
/app/constitution 体质辨识
/app/rnd          研发协同
/app/history      历史记录
/app/admin/...    管理后台
```

实现策略：

- 新增展示站页面，不直接覆盖现有业务页面逻辑。
- 将现有 `MainLayout` 继续作为工作台布局。
- 新增 `ShowcaseLayout` 或直接使用独立 `ShowcaseHomeView`。
- 登录成功后默认跳转到 `/app`。
- 未登录访问 `/app/**` 时仍跳转 `/login`。
- `/` 保持公开访问。

## 4. 推荐目录结构

```text
frontend/src/
├── assets/
│   └── showcase/
│       ├── textures/
│       ├── posters/
│       └── data/
├── components/
│   └── showcase/
│       ├── ShowcaseNav.vue
│       ├── ShowcaseHero.vue
│       ├── HeroKnowledgeScene.vue
│       ├── CapabilitySection.vue
│       ├── KnowledgeBaseMap.vue
│       ├── AgentPipeline.vue
│       ├── EvidenceTrustSection.vue
│       └── ShowcaseFooter.vue
├── styles/
│   └── showcase.css
└── views/
    └── showcase/
        └── ShowcaseHomeView.vue
```

原则：

- 展示站组件统一放在 `components/showcase/`。
- 展示站页面统一放在 `views/showcase/`。
- 展示站样式集中在 `styles/showcase.css` 或组件 scoped style 中。
- 不把展示站样式混入现有后台布局，避免影响 Element Plus 工作台。

## 5. 内容架构

### 5.1 首屏 Hero

核心文案：

```text
药食同源多智能体研发协同平台
以知识图谱为证据底座，让方剂替代、功效预测、风味优化、合规审查和体质食养推荐进入同一研发工作流。
```

首屏元素：

- 3D 知识图谱场景。
- 平台名称。
- 简短价值说明。
- 两个行动按钮：`进入工作台`、`查看能力演示`。
- 状态标签：`Neo4j 图谱证据`、`DeepSeek 生成`、`多 Agent 协同`、`药食同源合规`。

3D 场景建议：

- 中心节点：平台核心。
- 外围节点：Herb、Formula、Effect、Product、ComplianceRule、ConstitutionType。
- 节点之间用发光线段连接。
- 节点缓慢环绕，鼠标移动时轻微视差。
- 移动端降级为静态图谱视觉。

### 5.2 核心能力区

展示三条主线：

- 知识问答：面向药材、方剂、功效、风味、替代、合规证据检索。
- 体质辨识：面向九种体质测评、个体化食养建议、禁忌风险提醒。
- 研发协同：面向企业端产品研发、方剂改造、风味优化、替代映射和最终方案输出。

每个能力块使用一个真实业务问题：

```text
把四君子汤改造成药食同源代餐粉
麻黄可以用什么药食同源原料替代
孕妇能不能吃某某原料
这个配方是否好喝，适合做什么剂型
我是什么体质
```

### 5.3 八类知识库区

展示 KB1-KB8：

- KB1 药食同源原料合法性库
- KB2 功效-病症-性味归经库
- KB3 风味评价库
- KB4 单味药替代评分库
- KB5 名方/方剂知识库
- KB6 产品与市场库
- KB7 食品标准合规库
- KB8 九种体质辨识与食养规则库

交互建议：

- 鼠标悬停某个 KB 时，高亮关联节点和说明。
- 默认展示图谱底座的整体结构。
- 不展示旧 `Compound`、`ConsumerProfile`、`ConsumerSegment` 口径。

### 5.4 企业端与个人端分流区

企业端：

- 产品研发
- 名方/方剂药食同源化
- 单味药替代
- 风味优化
- 剂型工艺建议
- 竞品市场分析
- 合规审查

个人端：

- 九种体质辨识
- 个性化食养推荐
- 产品适配判断
- 禁忌风险提醒

展示方式：

- 使用双栏布局。
- 企业端偏研发流程和决策证据。
- 个人端偏体质档案和安全提醒。

### 5.5 Agent 流程区

展示当前研发协同 Agent 顺序：

```text
master_control
formula_generation
efficacy_prediction
flavor_prediction
replacement_mapping
master_control_final
```

视觉建议：

- 横向流程线。
- 每个 Agent 是一个步骤节点。
- 当前步骤 hover 后展开职责。
- 可用动效表现“需求进入、证据召回、Agent 协同、最终方案输出”。

### 5.6 证据可信区

展示系统为什么可信：

- 问题先分类。
- 实体先识别。
- 图谱先召回。
- 回答有证据摘要。
- LLM 异常有本地 fallback。
- 合规和禁忌有边界提醒。
- 不展示原始推理、提示词和内部 schema。

注意：

- 展示文案只能表达产品能力。
- 不泄露系统提示词。
- 不展示 `<think>`。
- 不展示 DeepSeek 原始 reasoning。

## 6. 视觉方向

关键词：

```text
知识图谱
药食同源
研发协同
可信证据
东方草本
现代科技
```

推荐色彩：

- 深墨绿：用于底色和科技氛围。
- 草本青：用于 Herb、合规、安全、生命力。
- 科技蓝：用于图谱线条、AI、数据流。
- 琥珀金：用于方剂、成果、重点信息。
- 中性灰白：用于正文、卡片、后台衔接。

避免：

- 全站单一蓝紫渐变。
- 大量无意义光球、漂浮装饰。
- 过度营销化的大卡片堆叠。
- 影响文字可读性的暗色背景。

## 7. Vibe Coding 工作方式

每次只推进一个明确切片。每个切片都包含：

```text
目标
文件范围
设计要求
交互要求
验收标准
```

推荐顺序：

1. 建立公开展示站路由和页面壳。
2. 完成展示站视觉 tokens 和导航。
3. 完成首屏静态版。
4. 接入 3D 知识图谱场景。
5. 完成核心能力区。
6. 完成 KB1-KB8 知识库区。
7. 完成企业端/个人端分流区。
8. 完成 Agent 流程区。
9. 完成证据可信区和页脚。
10. 增加响应式适配。
11. 增加 reduced-motion 降级。
12. 运行构建和浏览器截图验收。

## 8. 可直接使用的提示词

### 8.1 建立展示站路由

```text
请在当前 Vue 3 + Vite 项目中新增公开展示站首页。
要求：
1. 新增 / 路由作为公开展示站。
2. 将现有工作台首页迁移到 /app。
3. /login 保持公开。
4. /app/** 保持登录保护。
5. 不破坏现有 Chat、Rnd、Constitution、History、Admin 页面。
6. 新增 ShowcaseHomeView.vue，先只实现页面壳和导航。
7. 运行 npm run build 验证。
```

### 8.2 实现首屏静态版

```text
请实现展示站首屏 ShowcaseHero。
要求：
1. 文案聚焦“药食同源多智能体研发协同平台”。
2. 首屏第一屏必须直接出现品牌名和产品价值。
3. 不使用普通后台卡片风格。
4. 使用深墨绿、草本青、科技蓝、琥珀金组成视觉系统。
5. 增加进入工作台和查看能力演示按钮。
6. 桌面和移动端都不能出现文字溢出或遮挡。
7. 暂时用 CSS/SVG 图谱背景，不接 3D。
```

### 8.3 接入 3D 知识图谱

```text
请用 TresJS 为展示站首屏增加 3D 知识图谱场景。
要求：
1. 使用 three、@tresjs/core、@tresjs/cientos。
2. 新增 HeroKnowledgeScene.vue。
3. 中心节点表示平台核心。
4. 外围节点包含 Herb、Formula、Effect、Product、ComplianceRule、ConstitutionType。
5. 节点之间有轻量发光连线。
6. 场景要缓慢运动，但不影响文字阅读。
7. 移动端或 reduced-motion 下自动降级为静态背景。
8. 运行 npm run build，并用浏览器确认 canvas 非空。
```

### 8.4 实现核心能力区

```text
请实现展示站核心能力区 CapabilitySection。
要求：
1. 展示知识问答、体质辨识、研发协同三大能力。
2. 每个能力要配一个真实业务问题。
3. 点击能力按钮跳转到对应 /app 页面，如果未登录走现有登录保护。
4. 动效使用 @vueuse/motion 或 CSS transition，保持克制。
5. 不要使用嵌套卡片。
```

### 8.5 实现 KB1-KB8 区域

```text
请实现 KnowledgeBaseMap 组件。
要求：
1. 展示 KB1 到 KB8 的知识库名称和用途。
2. 风格要像知识图谱/证据底座，不要只是普通表格。
3. hover 某个知识库时，高亮其说明。
4. 不出现 Compound、ConsumerProfile、ConsumerSegment。
5. 移动端改为可扫描的纵向布局。
```

### 8.6 实现 Agent 流程区

```text
请实现 AgentPipeline 组件。
要求：
1. 展示 master_control、formula_generation、efficacy_prediction、flavor_prediction、replacement_mapping、master_control_final。
2. 每个节点展示中文角色名和一句核心职责。
3. 用流程线表现多 Agent 协作。
4. hover 或 focus 时展开更多说明。
5. 保证键盘可访问性。
```

### 8.7 做最终验收

```text
请对展示站做最终验收和修复。
要求：
1. 运行 npm run build。
2. 用浏览器检查桌面和移动端。
3. 检查 3D 场景是否非空、不卡顿、不遮挡文字。
4. 检查 prefers-reduced-motion 下复杂动画是否关闭或降级。
5. 检查中文文案是否正常显示。
6. 检查没有 console.error。
7. 检查页面没有展示 <think>、提示词、系统设定、JSON schema 字段。
8. 如有 frontend/dist 变化，在最终说明中说明。
```

## 9. 实现验收清单

功能验收：

- [ ] `/` 可公开访问展示站。
- [ ] `/login` 登录页正常。
- [ ] `/app/**` 登录保护正常。
- [ ] 工作台原有页面可正常进入。
- [ ] 展示站首屏有明确品牌和价值表达。
- [ ] 展示站按钮跳转正确。
- [ ] KB1-KB8 展示完整。
- [ ] Agent 流程展示完整。

视觉验收：

- [ ] 首屏第一视口有强视觉记忆点。
- [ ] 3D 场景不遮挡主文案。
- [ ] 页面不是普通后台卡片堆叠。
- [ ] 移动端布局不溢出。
- [ ] 长中文文本不被截断。
- [ ] 动效自然，不影响阅读。

安全与业务验收：

- [ ] 不展示提示词。
- [ ] 不展示 `<think>`。
- [ ] 不展示内部 schema。
- [ ] 不引入旧 `Compound` 主线。
- [ ] 不泄露 `.env` 或接口密钥。
- [ ] 不破坏现有知识问答和研发协同逻辑。

工程验收：

- [ ] `npm run build` 通过。
- [ ] 没有生产调试 `console.error`。
- [ ] 新增依赖已写入 `frontend/package.json`。
- [ ] 新增文件命名清晰。
- [ ] 展示站样式未污染后台页面。

## 10. 最小可交付版本

MVP 范围：

- 公开展示站首页。
- 首屏 Hero。
- CSS/SVG 或 TresJS 版知识图谱视觉。
- 三大核心能力区。
- KB1-KB8 区。
- Agent 流程区。
- 进入工作台按钮。
- 响应式适配。
- 构建通过。

MVP 之后再增强：

- 3D 场景更细致的节点交互。
- 滚动驱动相机动画。
- Remotion 生成展示站 fallback 视频。
- Rive 或 Lottie 小动效。
- 更完整的产品演示样例。
- 展示站独立部署配置。

## 11. 风险与规避

3D 性能风险：

- 首版控制节点数量。
- 移动端默认降级。
- 支持 `prefers-reduced-motion`。
- 不加载过大的模型和贴图。

视觉失控风险：

- 先做静态首屏，再接 3D。
- 每次只改一个区域。
- 每次改完都截图检查。

业务污染风险：

- 展示站组件和样式独立目录。
- 不修改后端 QA/RnD 核心逻辑。
- 不把展示站当成后台页面重构入口。

路由风险：

- 迁移 `/` 到 `/app` 时同步检查登录跳转。
- 所有 `/app/**` 继续走现有 auth guard。
- 不改动 API 封装和 Pinia 业务状态。

## 12. 推荐执行原则

- 先建立结构，再追求视觉。
- 先保证可读，再增加动效。
- 先静态表达清楚，再接入 3D。
- 每次只让模型实现一个组件。
- 每次都要求模型列出修改文件。
- 每次都运行构建或至少说明未运行原因。
- 每个视觉切片都用浏览器截图验收。
- 不让展示站改坏现有工作台。
