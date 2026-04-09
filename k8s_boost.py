import sqlite3, os, json, time, random, requests, re, zipfile, xml.etree.ElementTree as ET
from datetime import datetime

WORKSPACE = "/vol1/@apphome/trim.openclaw/data/workspace/exam-system"
RELAY_URL = "http://192.168.31.175:7892/chat"
DB_PATH = os.path.join(WORKSPACE, "exam.db")
LOG_PATH = os.path.join(WORKSPACE, "k8s_log.txt")
Q_TYPES = ["choice","judge","fill","short_answer"]
DIMS = ["命令","配置","原理","排错"]
NS = "urn:xmind:xmap:xmlns:content:2.0"

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = "[" + t + "] " + msg
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def _kids(node):
    if isinstance(node, dict):
        c = node.get("children", {})
        if isinstance(c, dict): return c.get("attached", [])
        return c if isinstance(c, list) else []
    return node.findall(f"{{{NS}}}children/{{{NS}}}topics[@type='attached']/{{{NS}}}topic")

def parse_xmind(path):
    results = []
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "content.json" in names:
                data = json.loads(z.read("content.json").decode("utf-8"))
                def walk(node, parent=""):
                    topic = node.get("title","").strip()
                    if not topic or len(topic)<3:
                        for c in _kids(node): walk(c, parent); return
                    notes = ""; nr = node.get("notes",{})
                    if isinstance(nr, dict):
                        plain = nr.get("plain",{})
                        if isinstance(plain, dict): notes = plain.get("content","")
                        elif isinstance(plain, str): notes = plain
                    elif isinstance(nr, str): notes = nr
                    ctx = (parent+" > "+topic) if parent else topic
                    results.append({"topic":ctx,"notes":notes if notes else topic,"path":parent})
                    for c in _kids(node): walk(c, ctx)
                for sheet in (data if isinstance(data,list) else [data]):
                    rt = sheet.get("rootTopic",{}); walk(rt,"")
            elif "content.xml" in names:
                root = ET.fromstring(z.read("content.xml").decode("utf-8"))
                def walk(node, parent=""):
                    te = node.find(f"{{{NS}}}title")
                    topic = (te.text or "").strip() if te else ""
                    if not topic or len(topic)<3:
                        for c in _kids(node): walk(c, parent); return
                    notes = ""
                    for ne in node.iter(f"{{{NS}}}notes"):
                        for pe in ne.iter(f"{{{NS}}}plain"):
                            ce = pe.find(f"{{{NS}}}content")
                            if ce is not None and ce.text:
                                notes = ce.text.strip(); break
                        if notes: break
                    ctx = (parent+" > "+topic) if parent else topic
                    results.append({"topic":ctx,"notes":notes if notes else topic,"path":parent})
                    for c in _kids(node): walk(c, ctx)
                for sheet in root.findall(f"{{{NS}}}sheet"):
                    rt = sheet.find(f"{{{NS}}}topic")
                    if rt is not None: walk(rt,"")
    except Exception as e:
        log("[错误] "+os.path.basename(path)+": "+str(e))
    return results

def relay(prompt, timeout=120):
    try:
        r = requests.post(RELAY_URL, json={"message":prompt,"history":[]}, timeout=timeout)
        reply = r.json().get("reply","")
        s = reply.find("["); e = reply.rfind("]")+1
        if s==-1: return []
        questions = json.loads(reply[s:e])
        if isinstance(questions,list) and questions: return questions
        return []
    except Exception as e:
        log("[relay错误] "+str(e)); return []

def save_question(conn, q, chapter):
    qt = q.get("q_type","choice")
    if qt not in Q_TYPES: qt = "choice"
    opts = q.get("options",[])
    if opts and isinstance(opts[0],str):
        opts = [{"letter":chr(65+i),"text":str(t)} for i,t in enumerate(opts[:4])]
    ans = q.get("answer","")
    if qt=="judge": ans = "正确"
    diff = random.choice([2,2,3,3,4])
    dim = random.choice(DIMS)
    q_text = q.get("question","")
    if not q_text: return False
    cur = conn.cursor()
    # 前150字符去重（更严格）
    cur.execute("SELECT 1 FROM question_bank WHERE substr(question,1,150)=? LIMIT 1",(q_text[:150],))
    if cur.fetchone(): return False
    cur.execute("INSERT INTO question_bank(source,chapter,topic,q_type,difficulty,dimension,question,answer,options,analysis,keywords,created_at,used_count,correct_rate) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,0)",
        ("K8S", chapter, q_text[:50], qt, diff, dim, q_text, ans,
         json.dumps(opts,ensure_ascii=False) if opts else None,
         q.get("analysis",""), q_text[:100], datetime.now().isoformat()))
    conn.commit()
    return True

def build_prompt(kps, chapter):
    parts = []
    for k in kps[:20]:
        parts.append("- "+k["topic"]+": "+k["notes"][:200])
    content = "\n".join(parts)
    return (
        f"基于K8S/Docker课程《{chapter}》，生成8道高质量习题（选择题、判断题、填空题、简答题混合），" +
        "涵盖命令/配置/原理/排错维度，难度2-4级。直接返回JSON数组，不要任何其他文字和markdown：\n" +
        "[\n" +
        '  {"q_type":"choice","question":"...","options":["A","B","C","D"],"answer":"B","analysis":"..."},\n' +
        '  {"q_type":"judge","question":"...","answer":"正确","analysis":"..."},\n' +
        '  {"q_type":"fill","question":"...用____填空","answer":"...","analysis":"..."},\n' +
        '  {"q_type":"short_answer","question":"...","answer":"...","analysis":"..."}\n' +
        "]\n知识内容：\n"+content[:3000]
    )

def main():
    log("=== K8S补强 启动 ===")
    conn = sqlite3.connect(DB_PATH)

    # 1. 清理现有K8S重复题（前150字符去重）
    log("清理K8S重复题...")
    cur = conn.cursor()
    cur.execute("SELECT id, substr(question,1,150) as qkey FROM question_bank WHERE source='K8S' ORDER BY id")
    seen = {}; deleted = 0
    for row in cur.fetchall():
        if row[1] in seen:
            conn.execute("DELETE FROM question_bank WHERE id=?", (row[0],))
            deleted += 1
        else:
            seen[row[1]] = row[0]
    conn.commit()
    log(f"  K8S删除了{deleted}条重复题")
    cur.execute("SELECT COUNT(*) FROM question_bank WHERE source='K8S'")
    log(f"  K8S剩余: {cur.fetchone()[0]}题")

    # 2. Docker文件跑4轮
    path = "/vol1/1000/云计算课件/第五阶段 云原生设计与实施docker&K8S/Docker容器.xmind"
    kps = parse_xmind(path)
    log(f"Docker共{len(kps)}知识点，跑4轮")
    total_new = 0
    for r in range(1, 5):
        log(f"--- 第{r}轮 ---")
        sample = random.sample(kps, min(15, len(kps)))
        prompt = build_prompt(sample, "Docker容器")
        questions = relay(prompt)
        if not questions:
            log("  [重试]"); time.sleep(5); questions = relay(prompt)
        if not questions:
            log("  [重试2]"); time.sleep(8); questions = relay(prompt)
        if not questions:
            log("  [放弃]"); continue
        saved = sum(save_question(conn, q, "Docker容器") for q in questions[:8])
        total_new += saved
        log(f"  入库{saved}题 (累计{total_new}题)")
        time.sleep(3)

    cur.execute("SELECT COUNT(*) FROM question_bank WHERE source='K8S'")
    log(f"K8S总计: {cur.fetchone()[0]}题")
    cur.execute("SELECT COUNT(*) FROM question_bank")
    log(f"题库总计: {cur.fetchone()[0]}题")
    conn.close()

if __name__ == "__main__":
    main()
