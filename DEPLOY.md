# 药食同源多智能体平台 — 生产部署运维手册

服务器：118.24.185.45（Tencent Cloud VM-0-9-opencloudos，OpenCloudOS 9.6 x86_64，2C/8G，根盘 80G）
生成：infra，2026-08-29（任务 T7）。无任何密码原文；凭据一律见 backups/creds.txt。

## 1. 目录结构

```
/www/wwwroot/neo4j-agents/
├── backend/           # 后端源码与生产 .env（root:root 0600）
├── frontend-dist/     # 前端构建产物（T6 nginx 站点根）
├── data/              # 预留数据目录
├── scripts/           # 运维脚本（backup.sh 700）
├── logs/backend/      # 应用层日志（logrotate 轮转）
├── logs/import/       # 导入/备份日志（logrotate 轮转）
├── backups/           # 凭据、每日备份、配置备份（见 §6）
└── deploy/nginx/      # nginx 相关配置与 DEPLOY.md
```

## 2. 组件版本与端口

| 组件 | 版本 | 安装方式 | 监听 | 说明 |
|---|---|---|---|---|
| PostgreSQL | 15.19 | dnf（非面板） | 127.0.0.1:5432 | 库 neo4j_agents，host 认证 scram-sha-256 |
| JDK | TencentKona OpenJDK 17.0.19 | dnf | - | /usr/lib/jvm/java-17-konajdk-17.0.19-1.oc9 |
| Neo4j | 5.26.1 社区版 | /opt/neo4j（tarball 布局） | 127.0.0.1:7687(bolt)/7474(http) | 仅本机；5.28.0 不可得，5.26.x 为 captain 批准的 fallback |
| 后端 FastAPI | 面板项目 neo4j-agents-backend | 宝塔 Python 项目（command） | 127.0.0.1:8000 | venv /www/server/pyporject_evn/neo4j-agents-backend |
| 前端 | 静态站（T6） | 宝塔 nginx | 80/443 | - |

## 3. 启停命令

后端（面板项目，推荐用面板）：
- 启动/停止/重启：宝塔面板「Python项目」页操作，或
  `btpython` 面板接口；直接启停进程用 `PythonProjectControl`（MCP）或面板 UI。
- 开机自启：面板 auto_run 已开。

Neo4j（systemd，root 执行）：
- `systemctl start|stop|restart neo4j`
- `systemctl status neo4j`
- 注意：stop 后后端 /api/health 首次调用可能 500（SessionExpired），数秒后驱动自愈。

PostgreSQL（systemd）：
- `systemctl start|stop|restart postgresql`（配置改动后用 `systemctl reload postgresql`）

nginx：只允许 `nginx -t && nginx -s reload`，禁止重启/停用面板核心服务。

## 4. 日志位置与轮转

- 后端应用日志：/www/wwwlogs/python/neo4j-agents-backend/error.log（面板托管，由面板自身机制管理）
- 导入日志：/www/wwwroot/neo4j-agents/logs/import/*.log（logrotate）
- 应用层日志：/www/wwwroot/neo4j-agents/logs/backend/*.log（logrotate）
- 备份日志：/www/wwwroot/neo4j-agents/logs/import/backup.log
- Neo4j 日志：/opt/neo4j/logs/*（Neo4j 内置轮转）；console 输出走 journald（journalctl -u neo4j）
- logrotate 配置：/etc/logrotate.d/neo4j-agents（daily / rotate 7 / compress / missingok / notifempty / copytruncate / size 10M）
- 验证：`logrotate -d /etc/logrotate.d/neo4j-agents`

## 5. 备份与恢复

每日 03:00 自动执行（宝塔计划任务 id=2「neo4j-agents-daily-backup」，shell：
`bash /www/wwwroot/neo4j-agents/scripts/backup.sh >> /www/wwwroot/neo4j-agents/logs/import/backup.log 2>&1`）。

单次产物（手工执行 `bash /www/wwwroot/neo4j-agents/scripts/backup.sh` 亦可）：
- backups/pg/neo4j_agents_YYYY-MM-DD.sql.gz（pg_dump，--no-owner --no-privileges）
- backups/neo4j/dump_YYYY-MM-DD/neo4j.dump（neo4j-admin database dump；社区版要求停库，脚本自动 stop→dump→start 并用 EXIT trap 兜底拉起）
- backups/env/.env.YYYY-MM-DD（0600）
- 保留策略：backups 下 mtime>7 天自动清理（creds.txt 与 infra-facts.txt 永不删除）

恢复：
- PG：`gunzip -c backups/pg/neo4j_agents_YYYY-MM-DD.sql.gz | psql -h 127.0.0.1 -U neo4j_agents -d neo4j_agents`（密码见 creds.txt）
- Neo4j（停库后执行）：`systemctl stop neo4j && sudo -u neo4j env JAVA_HOME=/usr/lib/jvm/java-17-konajdk-17.0.19-1.oc9 /opt/neo4j/bin/neo4j-admin database load neo4j --from-path=backups/neo4j/dump_YYYY-MM-DD --overwrite-destination=true && systemctl start neo4j`
- .env：`cp backups/env/.env.YYYY-MM-DD /www/wwwroot/neo4j-agents/backend/.env && chmod 600 ...`

## 6. 密码存放位置（只写位置，不写原文）

- /www/wwwroot/neo4j-agents/backups/creds.txt（0600，root）：PostgreSQL / Neo4j / 管理后台 admin 三组凭据
- /www/wwwroot/neo4j-agents/backend/.env（0600）：生产环境变量（含 DSN 与密钥）
- /www/wwwroot/neo4j-agents/backups/env/：.env 每日副本（0600）
- /www/wwwroot/neo4j-agents/backups/infra-facts.txt：无密码事实清单（版本/路径/端口）

## 7. 已知注意事项

- SSE：后端流式接口 /api/chat/.../messages/stream 需 nginx 反代关闭缓冲（proxy_buffering off）并调长 proxy_read_timeout（详见 deploy/nginx 配置）。
- Neo4j 内存上限：heap 512m/1g、pagecache 512m（/opt/neo4j/conf/neo4j.conf），8G 机器勿再上调。
- 夜间备份窗口：03:00 Neo4j 会短暂停库（数秒），期间后端 health 可能瞬时 500，属预期自愈。
- 面板 JDK 安装任务（jdk-17.0.8）长期卡 operation=3，可忽略；系统 Kona JDK 17 为实际运行时。
- pg_hba 已从 ident 改为 scram-sha-256（原文件备份 backups/pg_hba.conf.bak）。
- 导入脚本执行于 logs/import/，正式 --clear 前先确认 backups/neo4j_backups/ 已有回退产物。


## 域名与 HTTPs 待办（2026-08-29 记录）
- 域名绑定已完成：nginx server_name = 118.24.185.45 mmfh.com.cn www.mmfh.com.cn（站点 conf：/www/server/panel/vhost/nginx/118.24.185.45.conf；含域名版本副本：deploy/nginx/nginx.conf.domain）
- 现状：http://www.mmfh.com.cn/ 与 http://118.24.185.45/ 可访问；http://mmfh.com.cn/ 主域名被腾讯云"未备案拦截"302 到 dnspod.qcloud.com/static/webblock.html（云厂商网络层拦截，非 nginx 配置问题；服务器本机 Host 头验证为 200）
- 待办（用户 mmfh.com.cn 备案通过后执行）：
  1. 域名 A 记录已指向 118.24.185.45（一键解析，无需再改 DNS）
  2. 为站点申请 Let's Encrypt 证书（域名可用 SiteSSLApply/面板 UI；IP 需用面板"可信 IP 证书"）并加 80→443 redirect
  3. 注意：面板 SSL 相关操作可能重写 conf，务必保留 root=/www/wwwroot/neo4j-agents/frontend-dist、location / try_files 与 /api 反代（proxy_buffering off）自定义段；改动前先 cp 到 deploy/nginx/ 备份


## 2026-09 多用户账号服务（P4 上线记录，2026-08-29）

### 功能概览
- 开放注册 + 管理员审核启用：注册即创建 `app_user`（role=user, is_active=false），审核通过前无法登录。
- 登录/注册图形验证码（Pillow 绘制 PNG，内存 CaptchaStore，一次性，TTL 5 分钟，失败 5 次作废）。
- 多会话登录：每个 token 独立 `auth_session` 记录，互不踢；`auth_max_sessions_per_user` 超限时挤掉最旧会话。
- 用户管理后台（仅 admin）：增删改查、重置密码（撤销该用户全部会话）、启停、强制下线。
- chat/workflow 数据按用户隔离（`chat_session.user_id` / `workflow_session.user_id`）；admin 路由级守卫。
- 新表：`captcha_code`（预留 DB 版验证码存储，当前实现为内存 Store）；新列：`app_user.email`、`chat_session.user_id`、`workflow_session.user_id`。

### 新配置（backend/.env）
- `CAPTCHA_ENABLED`（默认 true）、`CAPTCHA_LENGTH`（4）、`CAPTCHA_TTL_SECONDS`（300）、`CAPTCHA_FAIL_MAX`（5）
- `LOGIN_FAIL_LOCK_MINUTES`（15）、`AUTH_SESSION_TTL_HOURS`、`AUTH_MAX_SESSIONS_PER_USER`（多会话上限）
- `DEFAULT_ADMIN_USERNAME` / `DEFAULT_ADMIN_PASSWORD`：种子管理员（首次启动用，已配置）

### 新增接口（前缀 /api）
- GET `/auth/captcha` → {captcha_id, image_base64}；POST `/auth/register`（body 含 captcha_id+captcha_text）
- POST `/auth/login`（body 含 captcha_id+captcha_text）、POST `/auth/change-password`、POST `/auth/logout`、GET `/auth/me`
- GET/POST `/admin/users`、PUT `/admin/users/{id}`（启停/改角色）、PUT `/admin/users/{id}/password`、POST `/admin/users/{id}/force-logout`、DELETE `/admin/users/{id}`
- 注意：get_current_admin 守卫在 main.py 路由级启用（/api/admin/* 全部需要管理员 Bearer token）。

### 验证码说明
- 图像由 PIL 绘制（120x40，噪点+干扰线），字体按 arial → DejaVuSans → msyh → simhei 顺序选用（本机为 /usr/share/fonts/dejavu/DejaVuSans.ttf）。
- 服务端只保存 sha256 摘要；一次性；IP 一致性校验（签发/校验 IP 不一致即失败）。
- 单 worker 内存实现（uvicorn 单进程命令启动，符合当前部署）；如改多 worker 需切换 `captcha_code` 表实现。

### 管理端用法
1. 登录页注册普通账号（需验证码）→ 等待审核。
2. 管理员（默认 admin）登录 → 侧边栏/路由 `/admin/users`（前端页面 UsersView，或直接调 API）。
3. 用户列表：启用/停用、改角色、重置密码、强制下线、删除；种子管理员不可降级；系统必须保留至少一名启用状态的 admin。

### 2026-08-29 P4 上线记录（deploy-qa）
- 上线前备份：`backups/pg/pre-multiuser-2026-08-292052.sql.gz`（pg_dump，gzip 校验 OK）；`backups/env/pre-multiuser.env`（600 root:root）。
- 上传：backend/app 41 文件 / 757,868 B；backend/requirements.txt、run_server.py、.env.example 3 文件 / 1,650 B；frontend-dist 9 文件 / 6,236,212 B（旧 asset 已清理）；backend/.env 前后 stat 一致（未触碰）。
- 依赖：venv pip 安装 `pillow 12.3.0`（其余已就绪），阿里云镜像。
- 重启：面板 PythonProjectControl restart → run=true, pid 203027, listen 8000。
- 线上验收：health（postgres/neo4j/llm 均 true）、captcha、register（等待审核）、未启用登录 401、admin 启用、登录 200、二次登录多会话不互踢、/admin/users 200、角色守卫 403、A/B chat 会话隔离 全部 PASS。
- **已知问题（已线上修复，代码待跟进）**：存量库 `auth_session.user_id` 为旧版 **UNIQUE INDEX**（ix_auth_session_user_id），P1 迁移 `ensure_auth_migration()` 只执行了 `DROP CONSTRAINT IF EXISTS`（对唯一索引无效），导致同一用户第二次登录 INSERT 违反唯一约束 → 500。已手动执行 `DROP INDEX ix_auth_session_user_id; CREATE INDEX ix_auth_session_user_id ON auth_session (user_id);` 修复。建议后续在 `init_db.ensure_auth_migration` 中先 `DROP INDEX IF EXISTS ix_auth_session_user_id` 再 `CREATE INDEX ...`（幂等），使该迁移对“旧唯一索引”库同样自愈。
- 前端：http://118.24.185.45/ 200，index.html 引用新资源 index-C5u7xQFa.js / index-DYavLUFN.css（200）；登录/注册/用户管理代码已入构建产物（bundle 内含 captcha/验证码/注册/admin/users 等字符串）；注册页以接口为准完成验收（POST /api/auth/register 200）。


## 2026-09 前端 UI 优化（P5 上线记录，2026-08-30）

### 本次改动（仅前端，后端未动、未重启）
- 首页图谱特写遮挡修复（commit fa432f73）：特写阶段视线淡出、链接聚焦、标签分层置顶、焦点球内部子网络展开减熵、bloom 收敛防过曝白斑。
- 登录页玻璃拟态深色系美化（commit 86acdb3e）：深色玻璃卡片（backdrop-filter blur(18px) saturate(140%)）、渐变标题（#34d399→#38bdf8 背景裁切文字）、验证码区域完善。

### 构建与上线（deploy-qa，2026-08-30）
- 构建：frontend `npm run build`（Vite 5.4.21），dist 共 9 文件。
- 新 hash 资源：`index-BzeEW-N2.js` / `index-CAw3ZOu8.css` / `HeroKnowledgeScene-zx47jhwI.js` / `HeroKnowledgeScene-BWCzd7E0.css` / `showcase-3d-D6giQCCZ.js`。
- 上传：整包 tar.gz 上传 → 清空 assets 旧 hash 资源后解包覆盖 `/www/wwwroot/neo4j-agents/frontend-dist`；目录权限规范化 755/644。
- 回滚点：`/www/wwwroot/neo4j-agents/frontend-dist.bak-20260830165443`（本次上线前完整状态：旧 index.html 引用 index-BGMWDLzP.js + 8 个旧资产，已核验）。

### 验收（全部 PASS）
- 本机（127.0.0.1:5173 dev）：Playwright 连拍 38 帧（前 12s 每秒 1 帧 + 之后 2s/帧至 64s，覆盖 intro 特写与完整轮播周期）；像素检查：最大近白占比 0.53%、最大白色连通块 0.14%（无过曝白斑），特写帧边缘结构清晰（Laplacian 方差 1111~2936），场景持续动画（帧间差异 3~21）；hero 文案 DOM 无重叠、全部可见；登录页玻璃卡片（backdrop-filter + 深色半透明背景）、渐变标题、验证码区域 DOM 检查 PASS；登录接口回归（captcha→login admin→me→logout）PASS。
- 公网：http://118.24.185.45/ 与 /login 均 200；新 hash 资源 200；/api/health 200（postgres/neo4j/llm 均 true）；登录冒烟（captcha→login 200→me 200→logout 200）PASS。
- 说明：旧 hash 资源已物理删除；直接请求旧资源命中 nginx `try_files` SPA 回退返回 index.html（200, text/html），属既有配置行为，无影响。
- 备注（非阻塞）：站点无 favicon，浏览器请求 /favicon.ico 404，属既有装饰性问题，后续可补。


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


## 2026-09 首页版块视觉升级（P7 上线记录，2026-08-31）

### 本次改动（仅前端，后端未动、未重启）
- commit ecb72622「feat: 展示版块 Three.js 基础设施与迷你场景组件」+ commit a204365f「feat: 首页三大版块 Three.js+3D+动态 CSS 优化」：
  - 新文件：`frontend/src/composables/useSectionThree.js`（迷你场景通用生命周期：low-power WebGLRenderer、DPR≤1.5、IntersectionObserver 视口启停、window blur/focus 暂停、reduced-motion 单帧静态、WebGL 失败回退）、`useTilt.js`（容器级 mousemove 事件委托 + rAF 插值 3D 倾斜、glare 跟随 `--tilt-gx/--tilt-gy`、hover 暂停空转、reduced-motion 自禁用）、`UseCaseScene.vue`（graph/constellation/pipeline 三变体）、`AudienceFlowScene.vue`、`AgentFlowScene.vue`。
  - 改动：`CapabilitySection.vue`（三卡微场景 + 倾斜 + 流程/统计/KB/示例文案增强）、`AudienceSplitSection.vue`（企业/个人双面板 + 分类器核心 + 分叉粒子流）、`AgentPipeline.vue`（6 步节点 + 能量脉冲 + 4s 自动轮播 + 点击交互 + 详情面板）。
- 性能守则：统一 DPR 上限 1.5、powerPreference=low-power、离视口暂停 rAF；页面 canvas 总数固定 6（hero1+cap3+aud1+pipe1），新增场景禁止常驻 canvas；reduced-motion / ≤640px 时三大版块回退 SVG/CSS（0 canvas）。

### 构建与上线（deploy-qa，2026-08-31）
- 构建：frontend `npm run build`（Vite 5.4.21），dist 共 9 文件（含 login-bg 三件套）。
- 新 hash 资源：`index-CDUurgba.js` / `index-AzZonmcz.css`（index.html 引用）、`showcase-3d-BbLLm7wP.js`（modulepreload）、`HeroKnowledgeScene-BmkO4RJu.js` + `HeroKnowledgeScene-DVgML9Jm.css`（主包动态 import chunk）。
- 回滚点：`/www/wwwroot/neo4j-agents/frontend-dist.bak-20260831000611`（上线前完整状态：index-DhdqM3mh.js + 旧资产 5 件，已核验）。
- 上线：SFTP 逐文件覆盖 → 清理旧 hash 资源 4 件（HeroKnowledgeScene-x0ezEfm_.js、index-CAw3ZOu8.css、index-DhdqM3mh.js、showcase-3d-CjTivXqx.js）→ 权限规范化 755/644。清理保留清单 = index.html 引用 + 主包 bundle 内动态 import 的 chunk（P6 教训已落实为部署脚本自动解析主包引用，不再依赖人工清单）；sha256 抽检 4 件 MATCH。

### 验收（全部 PASS，deploy-qa 2026-08-31）
- 本机（127.0.0.1:5173 dev，Edge headless，1440x900）：34/34 PASS，截图 `.tmp-showcase-t3/shots/`：
  - canvas 数：三大能力 3 / 分流 1 / 流程 1（页面总 6=hero1+cap3+aud1+pipe1）；每 canvas 连拍两帧非空像素 std 7.4~32.7、帧间差异 0.03~0.25（场景持续在动）。
  - 卡片倾斜：hover 后 transform=`perspective(900px) rotateX/rotateY` 非零、.tilt-hover 类生效、glare opacity=1；离开后 inline transform 清空复位。
  - 分流版块：分类器核心可见（classifierBreathe 4s + backdrop blur(14px)），粒子流通帧差 0.039。
  - 流程版块：能量脉冲帧差 0.27；4s 自动轮播焦点 1→2（名称/详情同步）；点击第 3 节点焦点与详情正确切换。
  - FPS 抽样 217（headless 无 vsync 上限，≫30 门槛）；console 零错误（仅既有 /favicon.ico 404 非阻塞，同 P5 记录）；无 failed request。
  - reduced-motion：全页 0 canvas，三版块 SVG/CSS 回退正常，轮播不推进；移动端 390px：0 canvas、无横向滚动（scrollWidth=390）。
- 生产浏览器级验证（Edge headless 打开公网首页）：canvas=6、cards=3、steps=6、hero 场景在、console 零错误。
- 公网：`http://118.24.185.45/` 200 且 index.html 引用新 bundle；9 个新资源全部 200（含动态 chunk，服务器 sha256 MATCH）；`/login` 200；`/api/health` 200（postgres/neo4j/llm_configured 均 true）；登录冒烟 captcha→login→me→logout 全 PASS。


## 2026-09 研发协同主控汇总报告化 + 证据与结果面板按 Agent 重构（P8 上线记录，2026-09-02）

### 本次改动（后端 + 前端）
- commit 0448cfb2「feat: 主控汇总 Agent 报告化与结构化配方输出（含 seed prompt/schema）」：
  `backend/app/db/seed_data.py` 新增 `RND_MASTER_FINAL_SCHEMA`（final_formula.composition 逐味 name/role/dose/rationale/basis/source、
  monarch_minister_summary、original_formula.changes 保留/替换/新增/删除、efficacy_summary、flavor_summary、compliance_risks、evidence_gaps），
  `rnd_master_control_final` prompt 改为「总结报告模式」（结论先行、证据可追溯、风险显式、下一步可执行）；
  `backend/app/services/rnd_workflow_orchestrator.py` 新增 `_assemble_final_report`（旧键兼容 + 结构化键优先取主控输出、缺失按模块 payload 抽取）、
  `_final_formula_section` / `_monarch_minister_summary` / `_original_formula_section` / `_efficacy_summary_section` / `_flavor_summary_section` 等。
- commit 6ffbe15f「feat: 研发协同证据与结果面板按 Agent 重构（含 dist）」：`frontend/src/views/portal/RndWorkspaceView.vue` 按 Agent 生成面板 tabs
  （主控=任务计划、方剂=配方组成+君臣佐使分组、功效=功效评估、风味=风味评估、替代=替代对比、主控汇总=最终方案），证据图谱 tab 仅在有快照 step 出现；
  `frontend/src/stores/rnd.js` 微调。

### 构建与上线（deploy-qa，2026-09-02）
- 上线前备份：`backups/pre-t3-rnd-report-20260902003356/app/db/seed_data.py`、`backups/pre-t3-rnd-report-20260902003356/app/services/rnd_workflow_orchestrator.py`（旧 sha256 记录于部署流程）；
  `frontend-dist.bak-20260902003356`（旧 assets 5 件：index-CDUurgba.js / index-AzZonmcz.css / HeroKnowledgeScene-BmkO4RJu.js / HeroKnowledgeScene-DVgML9Jm.css / showcase-3d-BbLLm7wP.js，已核验）。
- 上传：backend 2 文件（seed_data.py 32,744 B、rnd_workflow_orchestrator.py 65,245 B）sha256 均 MATCH；frontend-dist 4 文件
  （index.html / assets/index-DXeoezzh.js / assets/index-5F4MD3IX.css / assets/HeroKnowledgeScene-BOEHd5n6.js）sha256 均 MATCH；
  保留 HeroKnowledgeScene-DVgML9Jm.css、showcase-3d-BbLLm7wP.js（构建未变更）；清理旧资源 3 件（index-CDUurgba.js、index-AzZonmcz.css、HeroKnowledgeScene-BmkO4RJu.js）；
  权限规范化 755/644；backend/.env 未触碰。
- 重启：面板 PythonProjectControl restart → run=true, pid 1260310, listen 127.0.0.1:8000；启动日志「Application startup complete」无错误。
- 种子更新验证：prompt_template key='rnd_master_control_final' updated_at=2026-09-02 00:34(+08)（种子"存在则更新"路径），
  system_prompt 含「总结报告」模式，output_schema 含 final_formula / monarch_minister_summary 等新键（7 条 prompt 全表正常）。

### 验收（2026-09-02，deploy-qa）
- 真实工作流（admin 登录→POST /api/rnd/sessions→POST runs 问题「把四君子汤改造成药食同源代餐粉」→轮询 completed 6/6，run cd8ba932-d27c-47aa-8a13-4c96563300ee）：
  final_report 含全部新键（brief_summary/final_recommendation/consistency_checks/next_actions/task_plan/data_sources/final_formula/
  monarch_minister_summary/original_formula/efficacy_summary/flavor_summary/compliance_risks/evidence_gaps/modules）；
  final_formula.composition 4 味（炙甘草/人参/白术/茯苓）；original_formula 含 KB5 原方四君子汤/出处/保留替换新增删除；
  summary_metrics={stepCount:6, formulaCount:1, replacementCount:3, graphSnapshotCount:4}；6 个 step output_payload 关键字段齐全。
- 前端验收（公网 Edge headless，Playwright）：21/21 PASS —— 逐 Agent 点击 6 个步骤卡片，右侧面板 tabs 与内容均按 Agent 专属展示
  （主控=任务计划、方剂=配方组成+君臣佐使分组+原方依据、功效=功效评估、风味=风味评估、替代=替代对比+GNN/Baseline 双表、
  主控汇总=最终方案报告含最终配方/君臣佐使一览/原方依据/合规/证据缺口/下一步）；「最终方案」tab 仅主控汇总出现；
  证据图谱 tab 与有快照 step 完全一致（4 个 step）；console 零错误/零 pageerror；截图 `.tmp-rnd-t3/shots/`。
- 公网回归：`http://118.24.185.45/` 200 且引用新 bundle（index-DXeoezzh.js）；5 个资源全部 200；`/api/health` 200（postgres/neo4j/llm_configured 全 true）；
  登录冒烟 captcha→login→（token）PASS；QA 接口冒烟 GET/POST /api/chat/sessions 200、POST messages 200（返回结构化追问）；旧资源请求命中 SPA 回退（text/html，既有行为）。

### ⚠ 已知质量缺口（非阻塞上线，建议下轮处理）
- 主控汇总 final_formula.composition 的 role/dose 为占位符：「角色未标注」「剂量待结合原方出处与专业规范核定」（reason=None, basis=""）。
  根因链：图谱 KB5 context 已带 role_herbs（MONARCH_HERB/MINISTER_HERB/ASSISTANT_HERB/GUIDE_HERB）与配比文本（人参 9g 白术 9g 茯苓 9g 炙甘草 6g），
  但 `find_formulas_for_brief` 返回的 ingredients 中 IN_FORMULA 边 role 属性为「角色未标注」、dosage 为 null，方剂生成 Agent 与主控汇总 Agent 均沿用了该占位值。
  建议：neo4j_repository 侧把 role_relation 映射为君/臣/佐/使并写入组成条目（或注入建议剂量），并同步强化 step2/step6 prompt 的 role/dose 取值规范。

### 回滚点
- 后端：`cp backups/pre-t3-rnd-report-20260902003356/app/db/seed_data.py backend/app/db/`、`cp backups/pre-t3-rnd-report-20260902003356/app/services/rnd_workflow_orchestrator.py backend/app/services/` → 面板重启。
- 前端：`cp -a frontend-dist.bak-20260902003356/. frontend-dist/`（覆盖后旧 index.html 与旧资源即恢复）→ 无需重启（静态站）。


## 2026-09 配方角色/剂量占位修复（P8.1 上线记录，2026-09-02，deploy-qa）

### 本次改动（commit fa007555「fix: 配方君臣佐使与剂量来源映射修复，含 prompt 规范」）
- `backend/app/repositories/neo4j_repository.py`：新增 ROLE_RELATION_LABELS / map_role_relation（MONARCH_HERB→君药 等，占位符视为缺失）、
  clean_dose_value、parse_ratio_dosages（原方配比文本如「人参9g 白术9g 茯苓9g 炙甘草6g」→ {药材:剂量}）、
  enrich_formula_rows（find_formulas_for_brief 结果把 role_relation/原方君臣佐使字段/配比文本映射进 ingredients 的 role/dosage）。
- `backend/app/services/rnd_workflow_orchestrator.py`：配方 fallback 与组成抽取改用 map_role_relation/clean_dose_value（禁止占位符）；
  新增 `_enrich_composition`（composition 角色/剂量占位替换为图谱映射值或方剂学建议区间并附依据）、`_suggested_dose_for_herb`（人参 1-3g、君 6-9g、臣/佐 3-9g、使 1-3g）；
  `_final_formula_section` / `_monarch_minister_summary` 做角色归一。
- `backend/app/db/seed_data.py`：rnd_master_control_final / rnd_formula_generation prompt 增加 role 取值（君主佐使）与 dose（9g / 建议 9-15g）规范、禁止「角色未标注」「剂量待核定」。

### 上线（2026-09-02）
- 备份：`backups/pre-t5-role-dose-fix-20260902005459/app/{db,services,repositories}`（3 文件）。
- 上传：3 文件（seed_data.py 33,831 B / rnd_workflow_orchestrator.py 70,754 B / neo4j_repository.py 94,030 B）sha256 均 MATCH；服务器 py_compile OK。
- 重启：面板 restart → run=true pid=1265330 listen=127.0.0.1:8000；/api/health 200（postgres/neo4j/llm_configured 全 true）；本次启动后 0 ERROR/Traceback。
- 种子：rnd_formula_generation 与 rnd_master_control_final updated_at=2026-09-02 00:55(+08)，prompt 含 MONARCH_HERB→君药 映射与禁止占位符条款。

### t5 回归（同一问题「把四君子汤改造成药食同源代餐粉」，run b14a3b48-b359-49d5-981e-ed80cd4996e4，completed 6/6）
- final_formula.composition：炙甘草/使药/6g、人参/君药/9g、白术/臣药/9g、茯苓/佐药/9g（basis=原方配比解析，source=KB5 原方「四君子汤」）——占位符消除，PASS。
- monarch_minister_summary：使药=炙甘草/君药=人参/臣药=白术/佐药=茯苓，与 composition 一致，PASS。
- original_formula：KB5 原方四君子汤 + 出处 + changes（保留/替换/新增/删除），合规与证据缺口正常；summary_metrics={stepCount:6, formulaCount:1, replacementCount:3, graphSnapshotCount:4}。
- 前端最终方案 tab（公网 Edge headless）：25/25 PASS（配方表角色∈君主佐使、剂量含数值 6g/9g、君臣佐使一览一致、无占位符、console 0 错误）；截图 .tmp-rnd-t3/shots/step_主控汇总 Agent_final.png。

### ⚠ 遗留风险（建议下轮 hardening，非阻塞）
- 第一次回归运行（run 65c6c254）在 step3 失败：`_collect_formula_herbs` 对 `kb5_formula_context`（公式生成 LLM 输出）假设为 dict 数组，
  但 LLM 有时把该字段重述为字符串 → AttributeError: 'str' object has no attribute 'get' → 整 run failed（概率性）。
  已复测一次成功（6/6）后完成本记录；修复方向：`_run_formula_generation` 或 `_run_step` 输出处把 kb5_formula_context 规范化（仅保留 dict 项/丢弃字符串），
  并让 `_collect_formula_herbs` / `_formula_context_herb_names` / `_composition_from_formula` / `_enrich_composition` / `_final_formula_section` / `_original_formula_section` 对非 dict 项容错。


## 2026-09 kb5_formula_context 类型容错加固（P8.2 上线记录，2026-09-02，deploy-qa）

### 本次改动（commit b3d413e1「fix: kb5_formula_context 类型容错，防工作流偶发崩溃」，仅 rnd_workflow_orchestrator.py）
- 新增 `_safe_list` / `_safe_dict` / `_normalize_kb5_context`（str→json.loads 尝试，失败置空并 logger.warning）。
- `_collect_formula_herbs` / `_formula_context_herb_names` / `_formula_fallback` / `_composition_from_formula` / `_enrich_composition` /
  `_final_formula_section` / `_original_formula_section` / `_efficacy_summary_section` / `_flavor_summary_section` /
  `_collect_compliance_risks` / `_collect_evidence_gaps` / 替代对比相关路径全部改为类型安全遍历（非 dict 项跳过）。
- summary_metrics 的 formulaCount/replacementCount 使用 _safe_list 计数。

### 上线（2026-09-02）
- 备份：`backups/pre-t7-harden-20260902010840/app/services/rnd_workflow_orchestrator.py`。
- 上传：1 文件（74,753 B）sha256 MATCH；服务器 py_compile OK。
- 重启：面板 restart → run=true pid=1268656 listen=127.0.0.1:8000；/api/health 200（postgres/neo4j/llm_configured 全 true）；本次启动后 0 ERROR/Traceback/迁移报错（t6 未改 seed，prompt 与 00:55 版本一致）。

### t7 两连跑回归（同一问题「把四君子汤改造成药食同源代餐粉」，连续 2 次）
- run1=04681036-a6eb-4c26-9e7c-4fe035df5641、run2=3abdd98e-dac7-498f-99ac-679336aa72d4：均 completed 6/6、无 step failed（此前 t5 回归第 1 次在 step3 概率崩溃，本次加固后不再崩溃）。
- final_formula.composition（run2）：人参/君药/3-9g、白术/臣药/6-12g、茯苓/佐药/9-15g、炙甘草/使药/3-6g，无占位符；monarch_minister_summary 与配方一致；summary_metrics={stepCount:6, formulaCount:1, replacementCount:3, graphSnapshotCount:4}。
- 前端抽查（公网 Edge headless，run2）：25/25 PASS；截图 .tmp-rnd-t3/shots/（step_主控汇总 Agent_final.png 等）。

### ⚠ 遗留观察项（建议下一轮 backend-agent 处理，非阻断）
- 两连跑中公式生成 LLM 都把 kb5_formula_context 重述为非 JSON 散文（如「四君子汤源自《太平惠民和剂局方》…」），
  `_normalize_kb5_context` 正确置空 → 不再崩溃；但主控汇总 LLM 的 original_formula 输出仅填 changes、name/source 为空，
  导致最终方案「原方依据」专属区块（名称+出处+保留/替换/新增/删除表）未渲染（t5 回归 run b14a3b48 中 LLM 返回结构化 context 时该区块正常）。
  建议：step2 完成后由服务端把**查询侧**的结构化 kb5 context 回注到 formula 输出 payload（替换 LLM 回显字段），
  并让 `_original_formula_section` 在 LLM 缺 name/source 时用回注数据兜底（name=四君子汤、source=方剂学各论/《太平惠民和剂局方》宋）。


## 2026-09 original_formula 原方信息回注兜底（P8.3 上线记录，2026-09-02，deploy-qa）

### 本次改动（commit b8701321「fix: original_formula 原方信息查询侧回注」，仅 rnd_workflow_orchestrator.py）
- 新增 `_first_kb5_context`（取规范化后首个 kb5 context）与 `_kb5_source_text`（sources 优先、props.source 兜底）。
- `_original_formula_section`：LLM 输出仅填 changes 而缺 name/source 时，从 kb5_formula_context 回注 formula_name/source。

### 上线（2026-09-02）
- 备份：`backups/pre-t9-backfill-20260902012310/app/services/rnd_workflow_orchestrator.py`。
- 上传：1 文件（76,051 B）sha256 MATCH；服务器 py_compile OK。
- 重启：面板 restart → run=true pid=1272475 listen=127.0.0.1:8000；/api/health 200（postgres/neo4j/llm_configured 全 true）；本次启动后 0 ERROR/Traceback。

### t9 回归（同一问题「把四君子汤改造成药食同源代餐粉」，run f1f67288-9b07-4e1e-a926-4df718d51261，completed 6/6）
- final_formula：炙甘草/使药/6g、人参/君药/9g、白术/臣药/9g、茯苓/佐药/9g（basis=原方配比解析）；君臣佐使一览一致；summary_metrics={6,1,3,4}；无 step 失败。
- original_formula：name=四君子汤、source=方剂学各论、《太平惠民和剂局方》宋（本次 LLM 自行填充；changes：保留茯苓/替换3/删除甘草）。
- 前端最终方案 tab：25/25 PASS；「原方依据」区块渲染完整（名称/出处/保留/替换表/删除），截图 .tmp-rnd-t3/shots/t9_origin_formula_section.png。

### ⚠ 修复不完整（t8 判定 FAIL，建议 t10，非部署阻断）
- 单元级验证（verify_t8_backfill.py，直接调用 _original_formula_section）：
  - 结构化 kb5 context 场景：回注生效，name=四君子汤、source=方剂学各论、《太平惠民和剂局方》宋 → PASS；
  - **LLM 回显散文场景（t7 实证：约 2/3 概率出现）：_normalize_kb5_context 置空后回注源为空 → name/source 仍为空 → FAIL**。
- 根因：回注数据源取自 `formula_payload.kb5_formula_context`（即公式生成 LLM 回显字段），而非查询侧原始数据；LLM 将上下文转述为散文时该字段被 _normalize 置空，兜底失效。
- t10 建议：`_run_formula_generation` 中 `_run_step` 之后执行 `result["output_payload"]["kb5_formula_context"] = 查询侧 enrich 后的 formula_contexts`（服务端数据覆盖 LLM 回显），
  使 `_first_kb5_context`/`_composition_from_formula`/`_enrich_composition` 等下游始终拿到结构化 kb5 数据（名称/出处/role_herbs/ratio）。


## 2026-09 查询侧 kb5 上下文覆盖 LLM 回显（P8.4 上线记录，2026-09-02，deploy-qa）

### 本次改动（commit 89c7b9c5「fix: 查询侧 kb5 上下文覆盖 LLM 回显，原方信息回注封闭」，仅 rnd_workflow_orchestrator.py，21+/1-）
- `_run_formula_generation`：_run_step 之后调用 `_override_kb5_context_with_query_side(result, formula_contexts)` ——
  查询侧 enrich 后的 kb5 上下文覆盖 LLM 回显（服务端结构化数据优先）；LLM 回显另存 `_kb5_echo`（回显与结构化不同时）；
  查询侧为空则不覆盖。至此 t8 回注源闭环：`_first_kb5_context` 始终能拿到查询侧结构化数据。

### 上线（2026-09-02）
- 备份：`backups/pre-t11-override-20260902013130/app/services/rnd_workflow_orchestrator.py`。
- 上传：1 文件（77,210 B）sha256 MATCH；服务器 py_compile OK。
- 重启：面板 restart → run=true pid=1274567 listen=127.0.0.1:8000；/api/health 200（postgres/neo4j/llm_configured 全 true）；本次启动后 0 ERROR/Traceback。

### 封闭验证（本地单元级 verify_t10_closed_loop.py，3/3 PASS）
- t10 覆盖：LLM 散文回显被查询侧结构化替换，散文存 _kb5_echo → PASS。
- t8 回注闭环：LLM 只填 changes、name/source 为空 → 回注 name=四君子汤、source=方剂学各论、《太平惠民和剂局方》宋 → PASS。
- LLM 完全未填 → 同样回注查询侧值 → PASS。

### t11 真实 run（同一问题「把四君子汤改造成药食同源代餐粉」，run 35f97ee4-d305-42be-9db1-9b75e18885d5，completed 6/6）
- final_formula：人参/君药/3-9g、白术/臣药/6-12g、茯苓/佐药/9-15g、炙甘草/使药/3-6g（basis=原方配比解析），无占位符。
- original_formula：name=四君子汤、source=方剂学各论、《太平惠民和剂局方》宋（本次 LLM 自行填充；封闭验证证明 LLM 未填时亦可回注）。
- monarch_minister_summary 一致；summary_metrics={stepCount:6, formulaCount:1, replacementCount:3, graphSnapshotCount:4}；无 step 失败。
- 前端最终方案 tab：25/25 PASS；「原方依据」区块渲染完整（四君子汤（来源：方剂学各论、《太平惠民和剂局方》宋）+ 保留/替换表/删除）；
  console 0 错误；截图 .tmp-rnd-t3/shots/（t9_origin_formula_section.png = t11 run 状态）。

### 观察项（非阻塞，可选 t12）
- step2 持久化输出 payload 仍为 LLM 回显（t10 覆盖仅作用于内存中的下游数据流，_run_step 内部已 commit）：
  方剂生成面板的「原方依据」行来自 frontend 对 kb5_formula_context 的 Array.isArray 判断 → 回显散文时该面板回退显示 classic_reference（不报错）。
  如需彻底一致：可在 _run_step 返回前持久化覆盖后 payload（或覆盖后二次 commit）。

## 2026-09 第二轮账号与界面优化（P9 上线记录，2026-09-02，deploy-qa）

### 本次改动（t2–t6 五笔提交，含后端 2 文件 + 前端全量）
- 6f6e911b「feat: 修改密码增加图形验证码」：`backend/app/api/routes.py`（+6）、`backend/app/schemas/auth.py`（+3）——ChangePasswordRequest 增加 captcha_id/captcha_text，change-password 路由先验图形验证码（错误码 400，与登录同一 CaptchaStore/IP 一致性/一次性语义）。
- 6aaf3ce9「fix: 修复新账号历史记录归属/残留问题」（仅前端）：auth store setSession/clearSession 时 resetAll chat/rnd store；refreshSessions 拉取失败清空列表（宁空不残留）；登出/切号不再渲染上一账号会话。
- f36a0808「feat: 剩余页面英文适配全量补全」（仅前端）：admin 四页（Logs/Overview/Prompt/Template/Users）+ History/Rnd/Constitution/Account 等页面全量 i18n。
- ebffbfa9「feat: 体质辨识界面优化」（仅前端）：问卷卡片化、进度条/题号导航、结果卡、手动选择量表与标准量表测评双模式、i18n。
- a1e4aeb2「feat: 修改密码入口跳转个人中心+验证码+偏好设置卡片化」（仅前端）：右上角「修改密码」由弹窗改为跳转 /app/account?tab=security；安全页改密表单含验证码（错码提示+自动刷新）；偏好设置主题/语言卡片化。

### 构建与上线（deploy-qa，2026-09-02）
- 本地验证：py_compile routes.py/auth.py PASS；`scripts/validate_qa_routing.py` 17 用例全 PASS；`npm run build`（Vite 5.4.21）成功，新 hash：`index-BVbhVAst.js` / `index-BnTlgyQe.css` / `HeroKnowledgeScene-lkNFM12D.js`（HeroKnowledgeScene-DVgML9Jm.css 与 showcase-3d-BbLLm7wP.js 未变）。
- 回滚点：后端 `backups/pre-t7-round2-20260902174510/app/api/routes.py` + `app/schemas/auth.py`；前端 `frontend-dist.bak-20260902174540`（整目录，含旧 index.html 与旧资源）。
- 上传：backend 2 文件（routes.py 40,942 B / auth.py 2,125 B）sha256 MATCH、服务器 py_compile OK；frontend 4 文件（index.html + 3 新 hash 资源）sha256 MATCH；清理 9 个旧 hash 资源（保留清单 = index.html 引用 + 动态 chunk + login-bg 三件套）；权限 755/644；backend/.env 未触碰。
- 重启：面板 PythonProjectControl restart → run=true pid=1502631 listen=8000；/api/health 200（postgres/neo4j/llm_configured 全 true）；本次启动 0 Traceback/ERROR。

### 本机 dev(5173) Playwright 验收（43/43 PASS，截图 t7_accept/shots/）
- 中/英 × 浅/深四组合抽查：中文浅色全流程（登录→改密跳转+验证码→偏好卡片→聊天→历史→研发→体质双模式→个人中心→管理后台 4 页→登出）；英文浅色（登录/注册/菜单/改密/聊天/管理后台英文文案）；中文深色与英文深色（body 亮度 19、近白像素占比 ≤0.001，无刺眼浅色块）。
- 修改密码：右上角「修改密码」→ /app/account?tab=security；错误验证码 → 提示「验证码输入错误…验证码已自动刷新」且图片更换、输入清空；正确验证码+错误旧密码 → 「原密码不正确」（未改密码）。
- 偏好卡片：主题 3 卡（浅/深/跟随系统）切换 html.dark 即时生效；语言 2 卡切换 document.lang 即时生效。
- 体质辨识：手动量表 9 卡、保存档案→结果卡更新；标准量表（按类型过滤 3 题）进度 0/3→3/3→提交→结果卡+历史时间线（7 条）。
- 新账号隔离：A(admin) 建「孕妇能不能吃人参？」会话→登出→B(t7b_*) 登录，B 聊天侧栏/历史页均不含该会话，体质页无残留档案。
- console 全流程 0 错误。

### 公网回归（28/28 PASS，http://118.24.185.45）
- / 200 且引用新 bundle；5 个新资源 200；/login /register 200；/api/health 200（postgres/neo4j/llm_configured 全 true）。
- 登录冒烟：captcha OCR（服务器同款 DejaVuSans）→ admin 登录 200 → me/chat/sessions/rnd/sessions/constitution/types/admin/overview 全部 200。
- 改密冒烟：错误验证码 400「验证码输入错误…」；正确验证码+错误旧密码 400「原密码不正确」（未真改生产密码）。
- 新账号历史修复验证：注册 t7verify_* → 启用 → 登录 → chat/rnd 会话列表均 0 条（服务端 user_id 隔离 + 前端 store 清理双确认）→ 停用测试账号。
- 公网浏览器级：首页 canvas=6、登录页验证码渲染、console 0 错误；截图 t7_accept/shots/P1-prod-login.png / P2-prod-home.png。

### ⚠ 观察项（非阻塞，供下轮参考）
1. 聊天页「新建会话」在页面加载初期（自动选中最近会话完成前）点击，会被在途 auto-select 覆盖回旧会话；等列表稳定后点击正常。建议 ChatView 的 createNewSession 增加 auto-select 在途标志位互斥。
2. 本机验收期间注册接口命中限流 429（同 IP 短时间多次注册触发），属预期保护机制；验收脚本已改为复用既有测试账号。
3. Neo4j constitution 查询对 ConstitutionType.judgement_rule 的 UnknownPropertyKeyWarning（图谱属性缺失警告）为既有非阻塞项。

## 2026-09 首页分流区去斜线 + 研发流程渐变能量轨道重设计（P10 上线记录，2026-09-08）

### 本次改动（仅前端 4 组件）
- commit「feat: 首页分流区去斜线+研发流程渐变能量轨道重设计」：
  - `AudienceSplitSection.vue`：删除中央两条 ±7° CSS 斜线（`.classifier-line*` 全部模板/CSS/响应式）；
  - `AudienceFlowScene.vue`：删除 canvas 内两条静态贝塞尔 Line（保留曲线作粒子路径），粒子加大调柔（0.085→0.10）——分流区只保留「分类器核心 + 流动粒子」一种连接表达；
  - `AgentFlowScene.vue`：视觉层整体重写——1px 靛蓝线（#6366f1，游离于站点 token 外）替换为 TubeGeometry 双层「渐变能量轨道」（内层实色 vertexColors 翡翠绿 #059669→琥珀金 #d97706 + 外层 additive 辉光管）；单脉冲球升级为「彗星」（亮头 + 7 节渐隐尾迹，另有一枚相位差半圈的暗色环境彗星）；setActive 到达节点时触发扩散光环；**新增 pxUnit 屏幕恒定尺寸机制**（applySceneFit 缩放后按「屏幕像素→世界单位」反推管径/彗星/光环半径，修复扁长容器下线条缩成亚像素的根因）；修复到达光环在 boost 窗口到期后读取已重置 targetT 的 pageerror（位置/颜色触发时锁定）；
  - `AgentPipeline.vue`：`.step-connector` 虚线与 `.pipeline::before` 中线改为仅 `!useScene3d` 回退模式渲染（canvas 激活时由 3D 轨道承担连接）；step-node 底色改不透明渐变（含 hover/active 态），消除轨道透过 85% 玻璃卡形成的「删除线」感。

### 构建与上线（deploy-qa，2026-09-08）
- 本地：dev 5173 `accept_t3_showcase.py` 34/34 PASS（截图 `.tmp-showcase-t13/`）；`npm run build` 新 hash：`index-5FKKSM-t.js` / `index-C0O4xntb.css` / `showcase-3d-CCxkc7wr.js` + 动态 chunk `HeroKnowledgeScene-B1t_D0jI.js`（`HeroKnowledgeScene-DVgML9Jm.css` 未变）。
- 回滚点：`/www/wwwroot/neo4j-agents/frontend-dist.bak-20260908215410`（上线前完整状态：index-DLfjPMkS.js + 旧资产，已核验）。
- 上传：`deploy_t13_showcase_redesign_upload.py`（paramiko）9 文件 sha256 抽检 4 件 MATCH；清理旧资源 4 件（index-DLfjPMkS.js / index-BjeSgrr1.css / HeroKnowledgeScene-CBURvL24.js / showcase-3d-BbLLm7wP.js）；保留清单 = index.html 引用 + 主包动态 chunk（P6 教训已内置）；权限 755/644；静态站无需重启。

### 公网验收（2026-09-08，全部 PASS）
- `accept_t3_showcase.py --url http://118.24.185.45` **34/34 PASS**：canvas 总数 6（aud1+pipe1）、分类器核心可见 + classifierBreathe、轨道帧差 0.0136>0.001、4s 轮播推进、点击切换详情、FPS≥30、console/pageerror 0、reduced-motion 0 canvas + 轮播静止、390px 移动端 0 canvas 无横向滚动。
- 生产截图 `.tmp-showcase-t13-prod/`：分流区无斜线、流程区绿→金渐变轨道清晰（卡片间隙可见颜色过渡）、无文字「删除线」感。

## 2026-09 体质辨识题目/体质名/选项英文适配（P11 上线记录，2026-09-08）

### 本次改动（仅前端）
- 图谱 KB8 数据（题干/体质名/食养方向）为中文，i18n 之前只覆盖页面框架文案 → 切英文后题目仍是中文。
- 新增 `frontend/src/utils/constitutionEn.js`：CCMQ 量表通行英译映射——题干 30 条（按 question_code）、体质类型名 9 条、选项分数描述 5 条（图谱 score_1..5 为通用量表文案）、食养方向 9 条；`localizedText()` 统一「en-US 走映射、缺失回退中文原文」。
- `ConstitutionAssessmentPanel.vue`：题干（含题目地图/未答跳转 tooltip）、体质标签（题卡/结果主型/历史记录/分数字条）、选项描述、手动模式类型卡与食养方向、结果区食养方向全部按 locale 渲染；类型原值仍传给 typeColor/typeIconChar（配色不受影响）。
- 范围说明：测评历史 `result_summary`（后端生成的中文结论文本）与推荐/慎用原料（中药名，作为专有名词）暂保留中文。

### 上线（2026-09-08）
- 回滚点：`/www/wwwroot/neo4j-agents/frontend-dist.bak-20260908220742`（以实际时间为准，`ls -dt frontend-dist.bak-* | head -1`）。
- 上传：`deploy_t14_constitution_i18n_upload.py` 9 文件 sha256 抽检 MATCH；清理旧资源 3 件（index-5FKKSM-t.js / index-C0O4xntb.css / HeroKnowledgeScene-B1t_D0jI.js）；新 hash `index-D4_yKH04.js` / `index-BBazs1he.css` / `HeroKnowledgeScene-CriBNMwz.js`。
- 验证：dev(5173→生产 API 代理) 与公网双端 Playwright 实测——en-US 题干 "A.1-1 Do you feel full of energy?" / 选项 "Not at all" / 类型标签 "Balanced"；zh-CN 完整回归中文；两语言 0 pageerror。
