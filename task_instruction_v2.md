# AI Agent 自配置 MCP 服务 · 指令

> **你是 AI Agent**。你的任务：根据服务方提供的 `mcp_info.json`，为**自身**配置好 MCP 连接、安装相关Skills 并验证可用。
> 服务端的一切已经就绪，你只做：读取信息 → 处理证书（如需）→ 把凭证写入自身配置 → 下载安装 Skills。

---

## 输入：mcp_info.json

读取服务方提供的 `mcp_info.json`，字段如下：

| 字段 | 说明 |
|---|---|
| `api_token` | 接入凭证（Bearer Token），如 `btmcp_xxx` |
| `url` | MCP 访问地址，含安全路径前缀（若同时含 `local_host`/`public_host`，以你按「地址选择」选定的为准） |
| `local_host` | 内网/局域网访问地址（可选；与服务器同网段时用此地址） |
| `public_host` | 外网/公网访问地址（可选；跨网段/异地时用此地址） |
| `tls_required` | `true` / `false` — **是否需要处理证书链**（自签/私有 CA 证书时为 `true`） |
| `tls_cert` | 证书链 PEM **全文**（多行，仅 `tls_required=true` 时有值；可能含 叶子+中间+根 多张） |

> 文件可能还包含额外字段（如 `tls_cert_count` / `tls_self_signed` / `tls_san_matches` / `tls_cert_path`），仅为参考，不强制要求。

```json
{
  "api_token": "btmcp_-xSdXwrdgRczTiAxiWcoJqLHYZOFYdyYNVjqiGXTAdc",
  "public_host": "https://118.24.185.45:8765/bt-mcp-CI2jVOuMnOKP/mcp",
  "tls_required": false,
  "local_host": "https://10.6.0.9:8765/bt-mcp-CI2jVOuMnOKP/mcp"
}```

### 地址选择（公网模式时）

若同时给出 `local_host` 与 `public_host`，**必须按自身实际网络位置二选一**，后续所有配置用它作为 `url`：

- **与服务器同网段 / 内网可达** → 用 **`local_host`**（更快更稳）
- **公网 / 跨网段 / 异地**（云端 Agent、家中连机房）→ 用 **`public_host`**
- **不确定**：优先试 `local_host`，不通再换 `public_host`
- 所选地址须被证书 SAN 覆盖，否则连接报 `hostname/IP mismatch`，换另一地址即可
- 只有 `url` 一个字段时无需选择，直接用

---

## 第一步：确认自身身份（你是什么 Agent）

不同 Agent 的 MCP 配置路径和格式不同，**严禁混用**：

> **⚠️ 优先自查**：以下为参考索引，路径/格式可能随版本过时。请**优先查阅你（Agent）自身的官方最新文档**；官方文档不可访问或查不到时，用 **WebFetch** 工具检索（如搜索「<自身名> MCP http 配置」或抓取已知文档页）；仍查不到或不确定时，再使用本索引。

| Agent | MCP 配置路径 | 配置格式 | Skills 目录 | HTTP |
|---|---|---|---|---|
| Claude Code | **推荐 CLI 添加**：`claude mcp add --transport http baota-mcp <url> --header "Authorization: Bearer <api_token>"`；也可手写项目 `.mcp.json` / `.claude/settings.local.json`；用户 `~/.config/claude-code/mcp.json` | JSON `mcpServers` | `~/.claude/skills/`、`.claude/skills/` | ✅ |
| Codex | 用户 `~/.codex/config.toml`；项目 `.codex/config.toml` | TOML `[mcp_servers.*]` | `.agents/skills/`、`~/.codex/skills/` | ✅ |
| WorkBuddy | 用户 `~/.workbuddy/mcp.json`；项目 `.workbuddy/mcp.json` | JSON `mcpServers` | `~/.workbuddy/skills/` | ✅ |
| OpenClaw | `~/.openclaw/openclaw.json`（`mcp.servers`） | JSON `mcpServers` | `~/.openclaw/workspace/skills/` | ✅ |
| Hermes | `~/.hermes/config.yaml`（`mcp_servers:`） | YAML | `~/.hermes/skills/`、`.agents/skills/` | ✅ |
| Qoder | Win `%HOMEPATH%\.qoder\mcp.json`；项目 `.mcp.json` | JSON `mcpServers` | `~/.qoder/skills/`、`.qoder/skills/` | ⚠️ |
| Trae | 项目 `.trae/mcp.json`（**禁 AI 直写，须 UI 添加**）；用户 Win/mac | JSON `mcpServers` | `~/.trae/skills/`、`.trae/skills/` | ✅ |
| Cursor | 用户 `~/.cursor/mcp.json`；项目 `.cursor/mcp.json` | JSON `mcpServers` | 无原生 skills（用 `.cursor/rules`） | ✅ |
| LobsterAI | 应用 UI 配置 → 同步 `~/.openclaw/openclaw.json`（`nativemcp.servers`） | JSON | Skill Store → `~/.openclaw/workspace/skills/` | ✅ |

> ⚠️ 未完全确认项以官方最新文档为准。
>
> **Claude Code CLI 补充**：HTTP server 如需带环境变量（如证书信任 `NODE_EXTRA_CA_CERTS`），`claude mcp add` 用 `-e KEY=VALUE` 追加；查看已添加：`claude mcp list`。

> **重要**：以下 JSON 示例是 Claude Code 专用格式（含 `type: "http"` 字段）。如果你不是 Claude Code，格式可能完全不同，请先查阅自身文档再写入，**严禁硬编码路径和格式**。

---

## 第二步：提取证书内容（`tls_required=true` 时）

将 `tls_cert` 字段值**原样**写入本地文件 `baota_root_ca.crt`：

- 用 JSON 解析器读取（多行 PEM 在文件内是转义后的，解析后即还原为多行原文）
- **整份保存**，勿只提取第一张——该字段通常含**完整证书链**（叶子 + 中间 + 根）；叶子单独不是信任锚点，加了也验不通
- 若 `tls_required=false`，但实际连接仍报证书错误（如自定义证书也是自签），同样用 `tls_cert` 内容按下方方式处理

---

## 第三步：选择证书信任方式（`tls_required=true` 时）

以下方式平铺列出，**无优先级**，按自身情况选择（证书文件即第二步的 `baota_root_ca.crt`）。

**方式 A — 操作系统信任库**：把证书装进系统信任库，走系统信任链的客户端都有效。安装后需重启 MCP 客户端。

```bash
# macOS（当前用户，免 sudo）
security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain-db baota_root_ca.crt
# macOS（系统级）
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain baota_root_ca.crt
```

```powershell
# Windows（管理员 PowerShell）
Import-Certificate -FilePath baota_root_ca.crt -CertStoreLocation Cert:\LocalMachine\Root
# 或 certutil -addstore -f Root baota_root_ca.crt
```

```bash
# Linux Debian/Ubuntu
sudo cp baota_root_ca.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates
# Linux RHEL/CentOS/Fedora
sudo cp baota_root_ca.crt /etc/pki/ca-trust/source/anchors/ && sudo update-ca-trust
```

- **适用**：客户端使用系统信任链 / 可重启客户端 / 有相应权限。

**方式 B — 系统环境变量 `NODE_EXTRA_CA_CERTS`**：在操作系统环境变量中把该变量指向本地证书文件。部分 Node 系客户端忽略配置内 `env`，但读取系统环境变量（workbuddy 实测生效）。

```powershell
# Windows（用户级，免管理员；新进程生效，需重启客户端）
setx NODE_EXTRA_CA_CERTS "C:\Users\bt.cn\.workbuddy\baota_root_ca.crt"
# 或 PowerShell：
# [Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS", "C:\Users\bt.cn\.workbuddy\baota_root_ca.crt", "User")
```

```bash
# Linux / macOS（写入 shell 配置文件，重启客户端生效）
echo 'export NODE_EXTRA_CA_CERTS=/path/to/baota_root_ca.crt' >> ~/.bashrc   # 或 ~/.zshrc
```

- **适用**：Node 系客户端（workbuddy 等），配置内 `env` 不生效、但读取系统环境变量的场景。

**方式 C — 客户端配置 `env.NODE_EXTRA_CA_CERTS`**：在 Agent 的 MCP 配置 `env` 中把该变量指向本地证书文件。

- workbuddy 示例（证书保存到其配置目录）：

```json
{
  "mcpServers": {
    "baota-mcp": {
      "url": "https://<IP>:8765/bt-mcp-XXXX/mcp",
      "headers": {
        "Authorization": "Bearer <api_token>"
      },
      "env": {
        "NODE_EXTRA_CA_CERTS": "C:\\Users\\bt.cn\\.workbuddy\\baota_root_ca.crt"
      }
    }
  }
}
```

- **适用**：Node 系客户端（workbuddy、Claude Code 等），配置支持 `env` 且不便修改系统信任库。

**方式 D — 客户端跟随系统信任库（`NODE_OPTIONS=--use-system-ca`）**：Node ≥22 下让客户端读取系统信任库（配合方式 A 使用）。

```json
{
  "mcpServers": {
    "baota-mcp": {
      "type": "http",
      "url": "<url>",
      "headers": {
        "Authorization": "Bearer <api_token>"
      },
      "env": {
        "NODE_OPTIONS": "--use-system-ca"
      }
    }
  }
}
```

- **适用**：Node ≥22 客户端，已按方式 A 装好系统证书。

**方式 E — 跳过 TLS 验证（`NODE_TLS_REJECT_UNAUTHORIZED=0`）**：不验证证书，不安全。

```json
{
  "mcpServers": {
    "baota-mcp": {
      "type": "http",
      "url": "<url>",
      "headers": {
        "Authorization": "Bearer <api_token>"
      },
      "env": {
        "NODE_TLS_REJECT_UNAUTHORIZED": "0"
      }
    }
  }
}
```

- **适用**：仅临时连通测试 / 无法安装证书的场景。

> **选择说明**：以上方式平铺列出，无优先级。先确认自身（MCP 客户端）支持哪种机制再选对应方式，不确定时查阅自身文档，不要猜测。

---

## 第四步：写入自身配置

用 mcp_info.json 的 `api_token` 和「地址选择」中**选定的 `url`**（local_host / public_host 之一，只有一个 `url` 时直接用）填充配置。

### Claude Code 本地模式（`tls_required=false`）

在项目目录下创建/修改 `.claude/settings.local.json`：

```json
{
  "mcpServers": {
    "baota-mcp": {
      "type": "http",
      "url": "<url>",
      "headers": {
        "Authorization": "Bearer <api_token>"
      }
    }
  }
}
```

### Claude Code 公网模式（`tls_required=true`）

先按第三步完成证书信任（方式 A/B/C/D/E 任选其一），配置中**无需任何 TLS 跳过字段**：

```json
{
  "mcpServers": {
    "baota-mcp": {
      "type": "http",
      "url": "<url>",
      "headers": {
        "Authorization": "Bearer <api_token>"
      }
    }
  }
}
```

> 若按方式 C/D/E 在 `env` 中设置了变量，则在该 server 条目下保留对应 `env` 字段。

### Codex

配置路径：用户级 `~/.codex/config.toml`，或项目 `.codex/config.toml`（TOML `[mcp_servers.*]`）：

```toml
[mcp_servers.baota-mcp]
type = "http"
url = "<url>"
headers = { Authorization = "Bearer <api_token>" }
```

> 证书信任：Codex 为非 Node 系客户端，优先按第三步方式 A（系统信任库）处理；具体支持情况以自身官方最新文档为准（文档不可达时用 WebFetch 检索）。

### 其余 Agent

查阅自身文档，按其 MCP 配置格式写入 `url` + `Authorization: Bearer <api_token>`；workbuddy 类客户端注意证书走系统环境变量（方式 B）。官方文档不可达时，用 **WebFetch** 检索自身配置方法；不确定时查阅自身文档，不要猜测，严禁硬编码路径和格式。

---

## 第五步：安装 Skills

宝塔提供技能聚合包（一个 ZIP 内含多个技能文件夹），下载并解压到**自身**的 skills 目录：
- **Claude Code**：`~/.claude/skills`
- **Codex**：`~/.codex/skills/`（或项目 `.agents/skills/`）
- **其余 Agent**：查阅自身文档的技能目录，不要猜测

### 安装命令（按运行环境自动选择）

**Python（全平台通用，推荐）**：

```bash
python3 -c "
import urllib.request, zipfile, os, shutil
url = 'http://download.bt.cn/bt_mcp_install/bt-skills.zip'
dest = os.path.expanduser('~/.claude/skills')   # 非 Claude Code 时改为自身 skills 目录
os.makedirs(dest, exist_ok=True)
zip_path = os.path.join(dest, '_bt_skills.zip')
urllib.request.urlretrieve(url, zip_path)
with zipfile.ZipFile(zip_path) as zf:
    for member in zf.namelist():
        parts = member.split('/')
        # 取顶层文件夹名作为 skill 名
        if len(parts) >= 2 and parts[0] and not member.endswith('/'):
            target_dir = os.path.join(dest, parts[0])
            os.makedirs(target_dir, exist_ok=True)
            src = zf.open(member)
            target_file = os.path.join(target_dir, '/'.join(parts[1:]))
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            with open(target_file, 'wb') as dst:
                dst.write(src.read())
os.remove(zip_path)
print(f'Skills installed to {dest}')
"
```

**Windows PowerShell（无 Python 时）**：

```powershell
$url = "http://download.bt.cn/bt_mcp_install/bt-skills.zip"
$dest = "$env:USERPROFILE\.claude\skills"   # 非 Claude Code 时改为自身 skills 目录
$zip = "$env:TEMP\bt_skills.zip"
New-Item -ItemType Directory -Force -Path $dest
curl.exe -sSL -o $zip $url
Expand-Archive -Path $zip -DestinationPath $dest -Force
Remove-Item $zip
Write-Host "Skills installed to $dest"
```

> 聚合包结构示例：
> ```
> bt_skills.zip
>   ├── bt-site-manager/
>   │   ├── SKILL.md
>   │   └── ...
>   ├── bt-database-admin/
>   │   ├── SKILL.md
>   │   └── ...
>   └── bt-security-audit/
>       ├── SKILL.md
>       └── ...
> ```
>
> 解压后每个技能一个独立文件夹，AI Agent 自动识别并加载。

---

## 第六步：验证

配置完成后重启 MCP 客户端，并确认：

- [ ] 配置文件中 `url`（所选地址）与 `api_token` 与 mcp_info.json 一致
- [ ] 证书信任方式已生效（`tls_required=true` 时）
- [ ] 客户端能成功列出/调用 MCP 工具，无 TLS 或 401 错误
- [ ] Skills 已安装到自身 skills 目录并被识别

**常见失败排查**：

| 现象 | 原因与处理 |
|---|---|
| `401 Unauthorized` / `invalid token` | `api_token` 填错或失效；对照 mcp_info.json 重新填写 |
| `self-signed certificate` / `unable to verify` | 证书未信任；按第三步换一种方式（A/B/C/D） |
| `hostname/IP mismatch` | 证书 SAN 不覆盖 `url` 的域名/IP（如用 IP 连却用了别的域名）；改用匹配的地址或更换证书 |
| `ECONNREFUSED` / 连不上 | 服务未运行 / 端口未放行；联系服务方确认 |

---

## 完成

配置成功且验证通过后，输出简短确认（含 MCP URL、接入方式、证书信任方式、Skills 安装位置），供用户存档。
