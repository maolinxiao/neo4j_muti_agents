# -*- coding: utf-8 -*-
"""t7: 本地 DB 用户与会话抽查（只读）。"""
import psycopg

conn = psycopg.connect("postgresql://postgres:1234@localhost:5432/postgres")
cur = conn.cursor()
cur.execute("SELECT id, username, role, is_active, email FROM app_user ORDER BY username")
print("== app_user ==")
for r in cur.fetchall():
    print(r)
cur.execute("SELECT count(*) FROM chat_session")
print("chat_session count:", cur.fetchone()[0])
cur.execute("SELECT s.id, s.user_id, s.title FROM chat_session s ORDER BY s.created_at DESC LIMIT 10")
print("== recent chat sessions ==")
for r in cur.fetchall():
    print(r)
conn.close()
