import sys
from pathlib import Path

# 确保 backend 目录在 sys.path 中（面板托管启动时 CWD 不一定是项目目录）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="info")
