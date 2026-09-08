# -*- coding: utf-8 -*-
"""修复 auth_session.user_id 唯一索引：多会话需要普通索引（临时脚本）。

诊断：SELECT indexes on auth_session → 若 ix_auth_session_user_id 为 UNIQUE INDEX，
则 DROP 后重建为普通索引（幂等）。
"""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(hostname="118.24.185.45", port=22, username="root", password="mmfh2025KS686",
            timeout=30, banner_timeout=30, auth_timeout=30)


def run(sql):
    cmd = "sudo -u postgres psql -d neo4j_agents -Atc \"%s\"" % sql.replace('"', '\\"')
    _, out, err = cli.exec_command(cmd, timeout=120)
    return out.read().decode("utf-8", "replace"), err.read().decode("utf-8", "replace")


print("=== BEFORE ===")
out, _ = run("SELECT indexname || '|' || indexdef FROM pg_indexes WHERE tablename='auth_session' ORDER BY indexname")
print(out)

out, _ = run("SELECT indexdef FROM pg_indexes WHERE tablename='auth_session' AND indexname='ix_auth_session_user_id'")
is_unique = ("UNIQUE" in (out or "").upper())
print("[ix_auth_session_user_id unique?]", is_unique)

# 若唯一 → 删除并重建为普通索引；若非唯一 → 保持不变
if "ix_auth_session_user_id" in (out or ""):
    if is_unique:
        print("[fix] dropping unique index ...")
        print(run("DROP INDEX ix_auth_session_user_id")[0])
        print(run("CREATE INDEX ix_auth_session_user_id ON auth_session (user_id)")[0])
    else:
        print("[skip] index already non-unique")
else:
    print("[fix] index missing -> create")
    print(run("CREATE INDEX ix_auth_session_user_id ON auth_session (user_id)")[0])

print("=== AFTER ===")
out, _ = run("SELECT indexname || '|' || indexdef FROM pg_indexes WHERE tablename='auth_session' ORDER BY indexname")
print(out)

# 顺带核对 app_user / chat_session 的列（迁移情况）
out, _ = run("SELECT column_name || ':' || data_type FROM information_schema.columns WHERE table_name='app_user' ORDER BY ordinal_position")
print("[app_user columns]\n" + out)
out, _ = run("SELECT column_name FROM information_schema.columns WHERE table_name='chat_session' ORDER BY ordinal_position")
print("[chat_session columns]\n" + out)
cli.close()
