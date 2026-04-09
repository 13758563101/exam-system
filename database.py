"""数据库初始化与操作模块"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), 'exam.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS question_bank (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    source TEXT NOT NULL,\n"
        "    chapter TEXT NOT NULL,\n"
        "    topic TEXT,\n"
        "    q_type TEXT NOT NULL,\n"
        "    difficulty INTEGER DEFAULT 3,\n"
        "    dimension TEXT,\n"
        "    question TEXT NOT NULL,\n"
        "    options TEXT,\n"
        "    answer TEXT NOT NULL,\n"
        "    analysis TEXT,\n"
        "    keywords TEXT,\n"
        "    score INTEGER DEFAULT 10,\n"
        "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n"
        "    used_count INTEGER DEFAULT 0,\n"
        "    correct_rate REAL DEFAULT 0\n"
        ")"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS wrong_answers (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    q_id INTEGER REFERENCES question_bank(id) ON DELETE CASCADE,\n"
        "    wrong_count INTEGER DEFAULT 1,\n"
        "    last_wrong_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n"
        "    next_review_at TIMESTAMP,\n"
        "    mastery_level REAL DEFAULT 0,\n"
        "    review_interval INTEGER DEFAULT 1,\n"
        "    wrong_history TEXT DEFAULT '[]'\n"
        ")"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS exam_records (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    exam_type TEXT,\n"
        "    source TEXT,\n"
        "    total_count INTEGER,\n"
        "    correct_count INTEGER,\n"
        "    score REAL,\n"
        "    wrong_ids TEXT,\n"
        "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
        ")"
    )
    conn.commit()
    conn.close()
    _upgrade_tables()
    print("[DB] 初始化完成")


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, str) and v and v[0] in ('[', '{'):
            try:
                d[k] = json.loads(v)
            except Exception:
                pass
    return d


def add_question(source: str, chapter: str, topic: str, q_type: str,
                 question: str, answer: str,
                 options=None, analysis=None, keywords=None,
                 difficulty=3, dimension=None, score=10) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO question_bank "
        "(source,chapter,topic,q_type,question,options,answer,analysis,"
        "keywords,difficulty,dimension,score) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (source, chapter, topic, q_type, question,
         json.dumps(options, ensure_ascii=False) if options else None,
         answer, analysis, keywords, difficulty, dimension, score)
    )
    qid = cur.lastrowid
    conn.commit()
    conn.close()
    return qid


def get_question(qid: int) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM question_bank WHERE id=?", (qid,))
    row = cur.fetchone()
    conn.close()
    return row_to_dict(row) if row else None


def get_random_questions(source=None, exclude_ids=None, limit=10, q_types=None, interview_only=False) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    query = "SELECT * FROM question_bank WHERE 1=1"
    params: List[Any] = []
    if source:
        query += " AND source=?"
        params.append(source)
    if exclude_ids:
        ph = ','.join('?' * len(exclude_ids))
        query += f" AND id NOT IN ({ph})"
        params.extend(exclude_ids)
    if q_types:
        placeholders = ','.join('?' * len(q_types))
        query += f" AND q_type IN ({placeholders})"
        params.extend(q_types)
    if interview_only:
        query += " AND is_interview=1"
    query += " ORDER BY RANDOM() LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


def update_question_stats(qid: int, is_correct: bool):
    conn = get_conn()
    cur = conn.cursor()
    rate = 1.0 if is_correct else 0.0
    cur.execute(
        "UPDATE question_bank SET used_count=used_count+1,"
        "correct_rate=CASE WHEN used_count=0 THEN ? "
        "ELSE (correct_rate*used_count+?)/(used_count+1) END "
        "WHERE id=?",
        (rate, rate, qid)
    )
    conn.commit()
    conn.close()


def upsert_wrong_answer(q_id: int, user_answer: str = None, is_correct: bool = True):
    """SM-2 改良遗忘曲线算法"""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    intervals = [1, 3, 7, 14, 30]
    cur.execute("SELECT * FROM wrong_answers WHERE q_id=?", (q_id,))
    row = cur.fetchone()

    if row:
        mastery = row['mastery_level']
        wrong_count = row['wrong_count']
        history = json.loads(row['wrong_history'] or '[]')
        if is_correct:
            mastery = min(1.0, mastery + 0.2)
            review_interval = 999 if mastery >= 0.9 else intervals[min(wrong_count, len(intervals)-1)]
        else:
            wrong_count += 1
            mastery = max(0.0, mastery - 0.2)
            review_interval = intervals[min(wrong_count, len(intervals)-1)]
            history.append({"when": now.isoformat(), "answer": user_answer or ""})
        next_review = (now + timedelta(days=review_interval)) if review_interval < 999 else None
        cur.execute(
            "UPDATE wrong_answers SET wrong_count=?,mastery_level=?,review_interval=?,"
            "next_review_at=?,last_wrong_at=?,wrong_history=? WHERE q_id=?",
            (wrong_count, mastery, review_interval, next_review, now,
             json.dumps(history, ensure_ascii=False), q_id)
        )
    else:
        if is_correct:
            mastery, review_interval = 0.2, intervals[0]
            next_review = now + timedelta(days=review_interval)
            cur.execute(
                "INSERT INTO wrong_answers "
                "(q_id,wrong_count,last_wrong_at,next_review_at,mastery_level,review_interval,wrong_history) "
                "VALUES (?,0,?,?,?,?,'[]')",
                (q_id, now, next_review, mastery, review_interval)
            )
        else:
            wrong_count, mastery = 1, 0.0
            review_interval = intervals[0]
            next_review = now + timedelta(days=review_interval)
            history = [{"when": now.isoformat(), "answer": user_answer or ""}]
            cur.execute(
                "INSERT INTO wrong_answers "
                "(q_id,wrong_count,last_wrong_at,next_review_at,mastery_level,review_interval,wrong_history) "
                "VALUES (?,?,?,?,?,?,?)",
                (q_id, wrong_count, now, next_review, mastery, review_interval,
                 json.dumps(history, ensure_ascii=False))
            )
    conn.commit()
    conn.close()


def get_wrong_bank(limit=50, q_types=None) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    base = ("SELECT wb.*,q.question,q.q_type,q.options,q.answer,"
            "q.analysis,q.source,q.chapter,q.topic "
            "FROM wrong_answers wb "
            "JOIN question_bank q ON q.id=wb.q_id "
            "WHERE wb.mastery_level<0.9")
    params: List[Any] = []
    if q_types:
        placeholders = ','.join('?' * len(q_types))
        base += f" AND q.q_type IN ({placeholders})"
        params.extend(q_types)
    base += " ORDER BY wb.mastery_level ASC,wb.wrong_count DESC,wb.last_wrong_at ASC LIMIT ?"
    params.append(limit)
    cur.execute(base, params)
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


def mark_as_master(q_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM wrong_answers WHERE q_id=?", (q_id,))
    conn.commit()
    conn.close()


def add_exam_record(exam_type: str, source: str, total_count: int,
                    correct_count: int, score: float, wrong_ids: List[int]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO exam_records "
        "(exam_type,source,total_count,correct_count,score,wrong_ids) "
        "VALUES (?,?,?,?,?,?)",
        (exam_type, source, total_count, correct_count, score,
         json.dumps(wrong_ids, ensure_ascii=False))
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def get_exam_record(rid: int) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM exam_records WHERE id=?", (rid,))
    row = cur.fetchone()
    conn.close()
    return row_to_dict(row) if row else None


def get_stats() -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM question_bank")
    total_q = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM wrong_answers WHERE mastery_level<0.9")
    wrong_q = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM exam_records")
    total_exams = cur.fetchone()['cnt']
    conn.close()
    return {'total_questions': total_q, 'wrong_questions': wrong_q,
            'total_exams': total_exams}


# ========== Upgrade helpers ==========
def _upgrade_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(question_bank)")
    cols = [r[1] for r in cur.fetchall()]
    if "is_interview" not in cols:
        cur.execute("ALTER TABLE question_bank ADD COLUMN is_interview INTEGER DEFAULT 0")
    cur.execute("CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, q_id INTEGER UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()
    auto_tag_interview()

INTERVIEW_KEYWORDS = [
    "索引","事务","锁","进程","线程","IO","TCP","UDP","三次握手",
    "四次挥手","Socket","Shell三剑客","awk","sed","grep","find",
    "Dockerfile","PV","PVC","Pod","Deployment","Service","Ingress",
    "Replicaset","Nginx","负载均衡","Keepalived","LVS",
    "主从复制","binlog","redo log","undo log","MVCC","间隙锁",
    "explain","慢查询","join","优化","存储引擎","InnoDB","MyISAM"
]

def auto_tag_interview():
    conn = get_conn()
    cur = conn.cursor()
    tagged = 0
    for kw in INTERVIEW_KEYWORDS:
        cur.execute("""
            UPDATE question_bank SET is_interview=1
            WHERE is_interview=0
            AND (question LIKE ? OR analysis LIKE ? OR keywords LIKE ?)
        """, (f"%{kw}%", f"%{kw}%", f"%{kw}%"))
        tagged += cur.rowcount
    conn.commit()
    conn.close()
    return tagged

def get_favorites(limit=100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT q.* FROM question_bank q
        JOIN favorites f ON f.q_id=q.id
        ORDER BY f.created_at DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def add_favorite(q_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT OR IGNORE INTO favorites(q_id) VALUES (?)", (q_id,))
        conn.commit()
        added = cur.rowcount > 0
    except Exception:
        added = False
    conn.close()
    return added

def remove_favorite(q_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM favorites WHERE q_id=?", (q_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted

def is_favorite(q_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM favorites WHERE q_id=?", (q_id,))
    result = cur.fetchone() is not None
    conn.close()
    return result

def get_user_stats(days=30):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT source, COUNT(*) as total,
               SUM(CASE WHEN score >= 60 THEN 1 ELSE 0 END) as passed
        FROM exam_records
        WHERE created_at >= datetime('now', '-{days} days')
        GROUP BY source
    """)
    by_source = [dict(zip(["source","total","passed"], r)) for r in cur.fetchall()]
    cur.execute(f"""
        SELECT date(created_at) as day,
               ROUND(AVG(score),1) as avg_score, COUNT(*) as exams
        FROM exam_records
        WHERE created_at >= datetime('now', '-{days} days')
        GROUP BY day ORDER BY day
    """)
    daily = [dict(zip(["day","avg_score","exams"], r)) for r in cur.fetchall()]
    cur.execute("SELECT COUNT(*) FROM exam_records")
    total_exams = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM question_bank")
    total_q = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM wrong_answers WHERE mastery_level<0.9")
    wrong_q = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM favorites")
    fav_q = cur.fetchone()[0]
    conn.close()
    return {"by_source": by_source, "daily": daily,
            "total_exams": total_exams, "total_questions": total_q,
            "wrong_questions": wrong_q, "favorites": fav_q}

def get_weak_chapters(wrong_ids, limit=3):
    if not wrong_ids:
        return []
    conn = get_conn()
    cur = conn.cursor()
    placeholders = ",".join("?" * len(wrong_ids))
    cur.execute(f"""
        SELECT chapter, COUNT(*) as cnt
        FROM question_bank
        WHERE id IN ({placeholders})
        GROUP BY chapter
        ORDER BY cnt DESC LIMIT ?
    """, wrong_ids + [limit])
    result = [dict(zip(["chapter","cnt"], r)) for r in cur.fetchall()]
    conn.close()
    return result


if __name__ == '__main__':
    init_db()
