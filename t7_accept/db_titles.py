# -*- coding: utf-8 -*-
"""t7: 本地 DB 会话标题抽查。"""
import sys

sys.path.insert(0, r"D:\python_workspace\neo4j_muti_agents\backend\_vendor")
import psycopg

conn = psycopg.connect("postgresql://postgres:1234@localhost:5432/postgres")
cur = conn.cursor()
cur.execute("SELECT id, title, created_at FROM chat_session ORDER BY created_at DESC LIMIT 5")
for r in cur.fetchall():
    print(r)
conn.close()
