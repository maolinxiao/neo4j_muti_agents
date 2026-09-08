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

## 2026-09 研发需求 brief 可选展示与输入框回填（前端）
- RndWorkspaceView.vue：新增「显示当前 brief」开关（默认开）；无 brief 时显示空态占位；重载历史会话时研发需求输入框自动回填最近一次 run 的 question；新增 route.params.sessionId watch（会话切换也重新加载并回填）
- 提交：feat: 研发需求 brief 可选展示与历史会话输入框回填（本地仓库）
- 部署：frontend-dist.bak-brieffix-<ts> 为回滚点；新资源 index-DzHOZxJy.js / index-rN5PV44E.css；旧资源已清理（保留动态 chunk）

## 2026-09 知识问答会话操作菜单（置顶/重命名/删除/复制链接）
- 后端：ChatSession.pinned 列（幂等迁移 ensure_chat_session_migration）；PUT/DELETE /api/chat/sessions/{id}（归属校验+级联删除）；列表排序=pinned desc, updated_at desc
- 前端：ChatView 会话项悬停显示「⋯」下拉菜单（置顶/取消置顶、重命名弹窗、复制链接、删除确认）；置顶项高亮+图标；删除当前会话自动切换
- 提交：feat: 知识问答会话置顶/重命名/删除/复制链接（悬停操作菜单 + 后端接口与迁移）
- 部署：backend 5 文件(备份 .bak-*)+重启(迁移已验证 pinned 列)；frontend-dist.bak-chatmenu-* 回滚点；新资源 index-SEJ5k2a0.js / index-BhwpYYt1.css；API 冒烟全 PASS

## 2026-09 个人中心 + 暗色主题 + 中英文界面
- 后端：app_user.avatar_url、auth_session.user_agent/ip（幂等迁移）；PUT /auth/profile、POST /auth/avatar（PIL 裁方256 重编码PNG）、GET/DELETE /auth/sessions（+下线其他）、GET /auth/stats；/api/uploads 静态挂载（走 nginx /api 反代）；依赖新增 python-multipart
- 前端：AccountView 四 tab（资料/安全/统计/偏好）、全局暗色主题（html.dark + Element dark + CSS 变量 --app-*）、自研 i18n（zh-CN/en-US + el locale 切换）、MainLayout 头像+个人中心入口
- 部署：backend 7 文件上传+重启（迁移已验证 avatar_url/ip/user_agent）；frontend-dist.bak-account-* 回滚点；资源 index-ezaQ1Hg5.js/index-CzMhi2vg.css；冒烟：头像上传200+静态可访问、profile/sessions/stats 200
- 备注：i18n v1 已覆盖菜单/登录/注册/聊天核心/个人中心/管理用户；其余页面文案随 t() 接入逐步覆盖；主题/语言为设备级(localStorage)

## 2026-09 工作台首页重设计
- HomeView 重写：动态问候横幅（用户名+轨道装饰）、真实个人统计（/api/auth/stats 4 卡）、三大入口卡（图标/KB标签/CTA）、最近会话（点击直达）、快捷提问（预填问题跳转问答页）
- 联动：chat store 增加 pendingQuestion（快捷提问预填）；HomeView 全量 t()（新增 home.greeting/recentChats/viewAll/emptyRecent/quickAsk/enter 键 ×2 语言）；暗色 --app-* 变量适配
- 提交：feat: 工作台首页重设计；部署：frontend-dist.bak-home-* 回滚点；新资源 index-DLfjPMkS.js/index-BjeSgrr1.css；旧资源已清理
