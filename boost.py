#!/usr/bin/env python3
"""定向补强：给题数 < 10 的章节追加题目"""
import sqlite3, os, json, time, random, requests, re, zipfile, xml.etree.ElementTree as ET
from datetime import datetime

WORKSPACE = "/vol1/@apphome/trim.openclaw/data/workspace/exam-system"
RELAY_URL = "http://192.168.31.175:7892/chat"
DB_PATH = os.path.join(WORKSPACE, "exam.db")
LOG_PATH = os.path.join(WORKSPACE, "boost_log.txt")
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

def relay(prompt, timeout=120, retries=3):
    for attempt in range(retries):
        try:
            r = requests.post(RELAY_URL, json={"message":prompt,"history":[]}, timeout=timeout)
            reply = r.json().get("reply","")
            s = reply.find("["); e = reply.rfind("]")+1
            if s == -1:
                if attempt < retries-1: time.sleep(5); continue
                return []
            questions = json.loads(reply[s:e])
            if isinstance(questions, list) and questions: return questions
            if attempt < retries-1: time.sleep(5)
        except Exception as ex:
            log(f"[relay重试{attempt+1}] {str(ex)}")
            if attempt < retries-1: time.sleep(8)
    return []

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
    cur.execute("SELECT 1 FROM question_bank WHERE substr(question,1,150)=? LIMIT 1",(q_text[:150],))
    if cur.fetchone(): return False
    cur.execute("INSERT INTO question_bank(source,chapter,topic,q_type,difficulty,dimension,question,answer,options,analysis,keywords,created_at,used_count,correct_rate) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,0)",
        ("未知", chapter, q_text[:50], qt, diff, dim, q_text, ans,
         json.dumps(opts,ensure_ascii=False) if opts else None,
         q.get("analysis",""), q_text[:100], datetime.now().isoformat()))
    conn.commit()
    return True

def build_prompt(kps, chapter):
    parts = []
    for k in kps[:15]:
        parts.append("- "+k["topic"]+": "+k["notes"][:200])
    content = "\n".join(parts)
    return (
        f"基于云计算课程《{chapter}》，生成8道高质量习题（选择题、判断题、填空题、简答题混合），" +
        "涵盖命令/配置/原理/排错维度，难度2-4级。直接返回JSON数组，不要任何其他文字和markdown：\n" +
        "[\n" +
        '  {"q_type":"choice","question":"...","options":["A","B","C","D"],"answer":"B","analysis":"..."},\n' +
        '  {"q_type":"judge","question":"...","answer":"正确","analysis":"..."},\n' +
        '  {"q_type":"fill","question":"...用____填空","answer":"...","analysis":"..."},\n' +
        '  {"q_type":"short_answer","question":"...","answer":"...","analysis":"..."}\n' +
        "]\n知识内容：\n"+content[:3000]
    )

def main():
    log("=== 定向补强 启动 ===")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 找出题数 < 10 的章节
    c.execute("SELECT chapter, COUNT(*) as cnt FROM question_bank GROUP BY chapter HAVING cnt < 10 ORDER BY cnt ASC")
    low_chapters = [r[0] for r in c.fetchall()]
    log(f"题数<10的章节共 {len(low_chapters)} 个")

    # 所有XMind文件
    KB_DIR = "/vol1/1000/云计算课件"
    all_files = {}
    for root,dirs,fns in os.walk(KB_DIR):
        for fn in fns:
            if fn.endswith(".xmind"):
                all_files[fn.replace(".xmind","")] = os.path.join(root,fn)

    # 统计每个文件的题目数
    c.execute("SELECT chapter, COUNT(*) FROM question_bank GROUP BY chapter")
    chapter_counts = dict(c.fetchall())

    total_added = 0
    processed_files = set()

    # 遍历所有XMind文件，每文件检查是否包含低分章节，跑2轮
    for fname, fpath in all_files.items():
        kps = parse_xmind(fpath)
        if not kps: continue

        # 检查这文件里有哪些章节题数 < 10
        low_here = []
        for kp in kps:
            ch = kp["topic"].split(" > ")[-1]  # 取最后一个层级作为章节
            if chapter_counts.get(ch, 0) < 10:
                low_here.append(ch)

        # 如果有低分章节，跑2轮
        if low_here:
            # 判断source
            src = "未知"
            for key, val in [("第一阶段","Linux"),("第二阶段","MySQL"),("第三阶段","Shell"),("第四阶段","高并发"),("第五阶段","K8S")]:
                if key in fpath: src = val

            log(f"文件: {fname[:40]} | 低分章节: {len(set(low_here))}个 | 跑2轮")
            for rnd in range(1, 3):
                sample = random.sample(kps, min(15, len(kps)))
                chapter = fname[:30]  # 用文件名作为章节
                prompt = build_prompt(sample, chapter)
                questions = relay(prompt, retries=4)
                if questions:
                    saved = sum(save_question(conn, q, chapter) for q in questions[:8])
                    total_added += saved
                    log(f"  第{rnd}轮 入库{saved}题")
                else:
                    log(f"  第{rnd}轮 放弃")
                time.sleep(2)

        processed_files.add(fpath)

    # Git文件单独处理（特殊重试策略）
    git_files = [v for k,v in all_files.items() if "Git" in k or "git" in k]
    for fpath in git_files:
        fname = os.path.basename(fpath)
        log(f"=== Git专项: {fname}")
        kps = parse_xmind(fpath)
        if not kps: log("  无知识点"); continue
        # 用更少的知识点（5个）简化prompt
        for rnd in range(1, 4):
            sample = random.sample(kps, min(5, len(kps)))
            prompt = build_prompt(sample, "Git分布式版本控制")
            questions = relay(prompt, retries=5)
            if questions:
                saved = sum(save_question(conn, q, "Git分布式版本控制系统") for q in questions[:8])
                total_added += saved
                log(f"  第{rnd}轮 入库{saved}题")
                if saved > 0: break
            else:
                log(f"  第{rnd}轮 放弃")
            time.sleep(3)

    c.execute("SELECT COUNT(*) FROM question_bank")
    log(f"补强完成，新增{total_added}题，总计{c.fetchone()[0]}题")
    conn.close()

if __name__ == "__main__":
    main()
