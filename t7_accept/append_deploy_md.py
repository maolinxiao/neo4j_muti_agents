# -*- coding: utf-8 -*-
"""t7: 追加 DEPLOY.md 部署记录（服务器 + 本地）。"""
import os
import time

import paramiko

HOST = "118.24.185.45"
USER = "root"
PASSWORD = "mmfh2025KS686"
LOCAL_MD = r"D:\python_workspace\neo4j_muti_agents\DEPLOY.md"
REMOTE_MD = "/www/wwwroot/neo4j-agents/deploy/nginx/DEPLOY.md"

RECORD = """

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
"""


def main():
    record = RECORD.strip("\n") + "\n"
    # 本地
    with open(LOCAL_MD, "a", encoding="utf-8") as fh:
        fh.write("\n" + record)
    print("LOCAL_MD_APPENDED")

    # 服务器
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)
    sftp = cli.open_sftp()
    with sftp.open(REMOTE_MD, "a") as fh:
        fh.write("\n" + record)
    sftp.close()
    _, out, err = cli.exec_command(f"tail -c 400 {REMOTE_MD}", timeout=60)
    print("REMOTE_TAIL:", out.read().decode(errors="replace")[-300:])
    print("REMOTE_ERR:", err.read().decode(errors="replace")[:200])
    cli.close()
    print("DEPLOY_MD_OK")


if __name__ == "__main__":
    main()
