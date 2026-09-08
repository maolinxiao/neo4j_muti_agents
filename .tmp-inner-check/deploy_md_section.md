## 2026-09 特写内部展开重设计（P6 上线记录，2026-08-30）

### 本次改动（仅前端，后端未动、未重启）
- commit 2f9ea2f2「fix: 特写内部展开重设计（去连线+三环轨道小圆圈）」：
  - 去连线：删除 createInnerLink / INNER_TUBE_* / innerLinks 渲染与更新；config.links 数据字段保留不动（hero-inner-networks.json 未改）。
  - 三环轨道：新常量 INNER_RING_COUNT=3、INNER_RING_TILTS=[-0.42,0.08,0.52]（x/z/x 轴错开）、INNER_RING_RADIUS_STEP=0.18、INNER_RING_SPEEDS=[0.09,0.12,0.15]（交替方向）；新函数 innerRingOf/innerRingNodeCount/innerRingRadiusOf/ringPosition（index%3 轮询 + 环内等角 2π/n_i + 黄金相位 π(3−√5) + 节点种子）；替代 innerSpherePos/PLATFORM_INNER_LAYOUT/innerNodePosition。
  - 绽放展开：inner.group.scale 0.35→1.0（原 0.45→1.0），innerReveal>0.85 整体 ×1.06；卫星 opacity 0→1 同步揭示。
  - 标签朝向：dot(卫星世界方向, 相机视线) 背对淡出（≈0.2s exp 平滑）；沿用 labelEntries 按相机距离 renderOrder 分层。
  - 卫星球体半径 1.15→1.05（平台 0.96→0.90）；未破坏上一轮视线遮挡/链接聚焦/标签分层逻辑；减少动效偏好下公转 ×0.4、呼吸 ×0.5。

### 构建与上线（deploy-qa，2026-08-30）
- 构建：frontend `npm run build`（Vite 5.4.21），dist 共 9 文件。
- 新 hash 资源：`index-DhdqM3mh.js` / `index-CAw3ZOu8.css` / `HeroKnowledgeScene-x0ezEfm_.js` / `HeroKnowledgeScene-DVgML9Jm.css` / `showcase-3d-CjTivXqx.js`。
- 回滚点：`/www/wwwroot/neo4j-agents/frontend-dist.bak-20260830182321`（上线前完整状态，已核验）。
- 上线：SFTP 逐文件覆盖 frontend-dist → 清理旧 hash 资源 → 权限规范化 755/644。
- ⚠ 教训：`HeroKnowledgeScene-*.js/css` 是主包动态 import 的异步 chunk，不在 index.html 引用列表内；首轮清理按“保留 index.html 引用项”误删了这两个文件，已当场补传并 sha256 校验 MATCH。后续清理旧资源时必须把主包 bundle 内 mapDeps/动态 import 的 chunk 一并纳入保留清单（本次已线上修复，无影响）。

### 验收（全部 PASS）
- 本机（127.0.0.1:5173 dev，本机 Edge headless）：Playwright 连拍 32 帧（每 3-4s 一帧、共 132s，覆盖开场 + 完整 8 节点特写轮播周期；截图 `.tmp-inner-check/shots/frame_00..31.png`）。验收标准逐项：
  - 无连线：代码级（createInnerLink/innerLinks/INNER_TUBE 全部移除，grep 零命中）+ 像素级（特写帧无径向直线段；近球线段密度较旧版基线 64.0→38.1，残余为 cage/表面线框纹理误检）。
  - 三环轨道清晰可见：代码级（3 环子 Group、倾角/半径步进/交替公转）+ 像素级（frame_01/23 卫星绕大球多角度多半径分布，0.5r–1.7r 多带）。
  - 卫星均匀无聚堆：环内等角间距 + 黄金相位；像素级平均最小成对距离/r=0.40（优于旧版基线 0.22）。
  - 小标签无遮挡乱叠：标签面板两两 IoU 重叠检测，16 个特写帧全部为 0。
  - 画面无过曝白斑：近白占比最大 0.23%（旧基线 0.53%）、最大白色连通块 0.077%（旧基线 0.14%）。
  - 整体风格与之前一致：新旧特写帧 HSV 联合直方图相关性 0.9922（Bhattacharyya 距离 0.0824），亮度/色调分布同形。
  - 控制台仅 /favicon.ico 404（既有非阻塞）与 THREE.Clock deprecation 警告（非阻塞）。
- 公网：`http://118.24.185.45/` 200 且 index.html 引用新 bundle；5 个新资源全部 200（含动态 chunk，服务器 sha256 MATCH）；`/login` 200；`/api/health` 200（postgres/neo4j/llm_configured 均 true）；登录冒烟（captcha→login admin→me→logout）PASS（验证码 OCR 使用服务器同款 DejaVuSans.ttf 匹配）。
- 生产浏览器级验证（Edge headless 打开公网首页）：canvas 渲染正常、HeroGraphFallback 未启用、HeroKnowledgeScene chunk（js/css）被请求且控制台零错误。
