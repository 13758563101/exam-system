#!/usr/bin/env python3
"""大规模出题入库脚本 v2"""
import sys, os, json, time, random, sqlite3, requests, re, zipfile
from datetime import datetime

WORKSPACE = "/vol1/@apphome/trim.openclaw/data/workspace/exam-system"
KB_DIR = "/vol1/1000/云计算课件"
RELAY_URL = "http://192.168.31.175:7892/chat"
DB_PATH = os.path.join(WORKSPACE, "exam.db")
LOG_PATH = os.path.join(WORKSPACE, "batch_v2_log.txt")
Q_TYPES = ["choice","judge","fill","short_answer"]
DIMS = ["命令","配置","原理","排错"]
XMIND_MAP = {"第一阶段":"Linux","第二阶段":"MySQL","第三阶段":"Shell","第四阶段":"高并发","第五阶段":"K8S"}

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = "[" + t + "] " + msg
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + chr(10))
    except:
        pass

def _kids(node):
    c = node.get("children", {})
    if isinstance(c, dict):
        return c.get("attached", [])
    return c if isinstance(c, list) else []

def parse_xmind(path):
    """从XMind提取知识点：用topic title作为知识内容"""
    try:
        with zipfile.ZipFile(path) as z:
            data = json.loads(z.read("content.json").decode("utf-8"))
            results = []
            def walk(node, parent=""):
                topic = node.get("title", "").strip()
                # 跳过空标题或太短的标题（可能是导航节点）
                if not topic or len(topic) < 3:
                    for child in _kids(node):
                        walk(child, parent)
                    return
                # 尝试取notes内容（可能在plain.content里）
                notes = ""
                notes_raw = node.get("notes", {})
                if isinstance(notes_raw, dict):
                    plain = notes_raw.get("plain", {})
                    if isinstance(plain, dict):
                        notes = plain.get("content", "")
                    elif isinstance(plain, str):
                        notes = plain
                elif isinstance(notes_raw, str):
                    notes = notes_raw
                # 拼装完整路径作为上下文
                context = (parent + " > " + topic) if parent else topic
                if notes:
                    results.append({"topic": context, "notes": notes.strip(), "path": parent})
                else:
                    # 用title作为知识点内容
                    results.append({"topic": context, "notes": topic, "path": parent})
                for child in _kids(node):
                    walk(child, context)
            sheets = data if isinstance(data, list) else [data]
            for sheet in sheets:
                rt = sheet.get("rootTopic", {})
                walk(rt, "")
            return results
    except Exception as e:
        log("[xmind错误] " + os.path.basename(path) + ": " + str(e))
        return []

def guess_src(path):
    for k,v in XMIND_MAP.items():
        if k in path: return v
    return "Linux"

def guess_chapter(path):
    name = os.path.basename(path).replace(".xmind","")
    for k in XMIND_MAP: name = name.replace(k,"")
    name = re.sub(r"^第.+?章[- ]?","",name)
    return name.strip("- ").strip() or "综合"

def relay(prompt, timeout=120):
    try:
        r = requests.post(RELAY_URL, json={"message":prompt,"history":[]}, timeout=timeout)
        reply = r.json().get("reply","")
        s = reply.find("["); e = reply.rfind("]")+1
        if s == -1: return []
        questions = json.loads(reply[s:e])
        if isinstance(questions, list) and questions:
            return questions
        return []
    except Exception as e:
        log("[relay错误] " + str(e))
        return []

SRC = "Linux"
CH = "综合"

def save_question(conn, q):
    global SRC, CH
    qt = q.get("q_type","choice")
    if qt not in Q_TYPES: qt = "choice"
    opts = q.get("options",[])
    if opts and isinstance(opts[0], str):
        std = [{"letter":chr(65+i),"text":str(t)} for i,t in enumerate(opts[:4])]
        opts = std
    ans = q.get("answer","")
    if qt == "judge": ans = "正确"
    diff = random.choice([2,2,3,3,4])
    dim = random.choice(DIMS)
    q_text = q.get("question","")
    if not q_text: return False
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM question_bank WHERE substr(question,1,100)=? LIMIT 1",(q_text[:100],))
    if cur.fetchone(): return False
    cur.execute("INSERT INTO question_bank(source,chapter,topic,q_type,difficulty,dimension,question,answer,options,analysis,keywords,created_at,used_count,correct_rate) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,0)",
        (SRC, CH, q_text[:50], qt, diff, dim, q_text, ans,
         json.dumps(opts,ensure_ascii=False) if opts else None,
         q.get("analysis",""), q_text[:100], datetime.now().isoformat()))
    conn.commit()
    return True

def build_prompt(src, ch, kps):
    parts = []
    for k in kps[:20]:
        parts.append("- " + k["topic"] + ": " + k["notes"][:200])
    content = chr(10).join(parts)
    return (
        "基于" + src + "课程《" + ch + "》，生成8道高质量习题（选择题、判断题、填空题、简答题混合），" +
        "涵盖命令/配置/原理/排错维度，难度2-4级。直接返回JSON数组，不要任何其他文字和markdown：" + chr(10) +
        "[" + chr(10) +
        '  {"q_type":"choice","question":"...","options":["A","B","C","D"],"answer":"B","analysis":"..."},' + chr(10) +
        '  {"q_type":"judge","question":"...","answer":"正确","analysis":"..."},' + chr(10) +
        '  {"q_type":"fill","question":"...用____填空","answer":"...","analysis":"..."},' + chr(10) +
        '  {"q_type":"short_answer","question":"...","answer":"...","analysis":"..."}' + chr(10) +
        "]" + chr(10) + "知识内容：" + chr(10) + content[:3000]
    )

def main():
    global SRC, CH
    log("=== 大规模出题 v2 启动 ===")
    conn = sqlite3.connect(DB_PATH)
    files = []
    for root,dirs,fns in os.walk(KB_DIR):
        for fn in fns:
            if fn.endswith(".xmind"):
                files.append(os.path.join(root,fn))
    files = sorted(set(files))
    log("找到XMind文件: " + str(len(files)))
    total_new = 0
    fail = 0
    for i, xf in enumerate(files):
        SRC = guess_src(xf)
        CH = guess_chapter(xf)
        log("[" + str(i+1) + "/" + str(len(files)) + "] " + SRC + " - " + CH)
        kps = parse_xmind(xf)
        if not kps:
            log("  [跳过] 无知识点"); fail += 1; time.sleep(1); continue
        log("  知识点" + str(len(kps)) + "个，发送relay请求...")
        sample = random.sample(kps, min(15, len(kps)))
        prompt = build_prompt(SRC, CH, sample)
        questions = relay(prompt)
        if not questions:
            log("  [重试]"); time.sleep(5); questions = relay(prompt)
        if not questions:
            log("  [放弃]"); fail += 1; time.sleep(3); continue
        saved = sum(save_question(conn, q) for q in questions[:8])
        total_new += saved
        log("  入库" + str(saved) + "题 (本次" + str(total_new) + "题)")
        if (i+1) % 10 == 0:
            cur = conn.cursor(); cur.execute("SELECT COUNT(*) FROM question_bank")
            log("  >> 当前总计: " + str(cur.fetchone()[0]) + "题")
        time.sleep(2)
    cur = conn.cursor()
    cur.execute("SELECT source, COUNT(*) FROM question_bank GROUP BY source ORDER BY COUNT(*) DESC")
    log("")
    log("=== 完成 === 新增:" + str(total_new) + "题 失败:" + str(fail))
    for r in cur.fetchall():
        log("  " + r[0] + ": " + str(r[1]) + "题")
    cur.execute("SELECT COUNT(*) FROM question_bank")
    log("总计: " + str(cur.fetchone()[0]) + "题")
    conn.close()

if __name__ == "__main__":
    main()
