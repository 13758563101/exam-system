#!/usr/bin/env python3
"""遗忘曲线定时提醒 - 通过 QQ Bot 推送"""
import sys, os, sqlite3, requests
sys.path.insert(0, os.path.dirname(__file__))
import database

RELAY_URL = "http://192.168.31.175:7892/chat"
BOT_OPENID = "16326025576647662382"  # 雷神Bot openid

def check_and_remind():
    conn = sqlite3.connect(database.DB_PATH)
    cur = conn.cursor()
    from datetime import datetime
    now = datetime.now().isoformat()
    cur.execute("""
        SELECT COUNT(*)
        FROM wrong_answers
        WHERE next_review_at IS NOT NULL
        AND datetime(next_review_at) <= datetime(?)
        AND mastery_level < 0.9
    """, (now,))
    count = cur.fetchone()[0]
    conn.close()

    if count > 0:
        msg = chr(0x1F4DA) + " 雷神提醒：有 " + str(count) + " 道题该复习了！" + chr(10) + "快去做一套每日一练巩固知识点吧 " + chr(0x1F447) + chr(10) + chr(0x1F517) + " http://192.168.31.96:7758/"
        try:
            r = requests.post(RELAY_URL, json={
                "message": "[系统] " + msg,
                "user_id": BOT_OPENID,
                "history": [],
                "timeout": 30
            }, timeout=35)
            print("[Scheduler] 推送成功: " + str(count) + "题待复习")
        except Exception as e:
            print("[Scheduler] 推送失败: " + str(e))
    else:
        print("[Scheduler] 无待复习题目")

if __name__ == "__main__":
    check_and_remind()
def weekly_import():
    """每周自动批量入库（每周日晚上10点执行）"""
    import subprocess, os
    workspace = "/vol1/@apphome/trim.openclaw/data/workspace/exam-system"
    log_file = os.path.join(workspace, "auto_import.log")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            from datetime import datetime
            t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n[{t}] === 每周自动入库开始 ===\n")
            f.flush()
        result = subprocess.run(
            ["python3", "boost.py"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=7200
        )
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(result.stdout[-2000:] if result.stdout else "")
            if result.returncode != 0:
                f.write(f"[错误] {result.stderr[-500:]}\n")
        import sqlite3
        conn = sqlite3.connect(os.path.join(workspace, "exam.db"))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM question_bank")
        before = c.fetchone()[0]
        c.execute("CREATE TABLE IF NOT EXISTS _keep_ids (id INTEGER PRIMARY KEY)")
        c.execute("INSERT INTO _keep_ids(id) SELECT MIN(id) FROM question_bank GROUP BY substr(question,1,100)")
        c.execute("DELETE FROM question_bank WHERE id NOT IN (SELECT id FROM _keep_ids)")
        c.execute("DROP TABLE _keep_ids")
        conn.commit()
        after = c.fetchone()[0]
        conn.close()
        removed = before - after
        with open(log_file, "a", encoding="utf-8") as f:
            from datetime import datetime
            t2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{t2}] 入库完成！总计{after}题，新增{after-removed if removed else 0}题，去重{removed}题\n")
        print(f"[AutoImport] 本次入库完成，去重{removed}题，当前总计{after}题")
    except Exception as e:
        with open(log_file, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 入库异常: {e}\n")
        print(f"[AutoImport] 入库异常: {e}")
