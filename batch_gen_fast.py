#!/usr/bin/env python3
"""快速批量生成 - 直接用 /chat 端点，每次生成1道题"""
import sys, os, json, random, time, requests
sys.path.insert(0, os.path.dirname(__file__))
import question_generator, database

RELAY_URL = "http://192.168.31.175:7892/chat"
Q_TYPES = ['choice', 'judge', 'fill', 'short_answer']
DIMENSIONS = ['命令', '配置', '原理', '排错']
DIFFICULTIES = [2, 3, 3, 4, 4]
TARGET = 200

def gen_one(topic, content, source, chapter, q_type, dimension, diff):
    prompt = f"基于以下{source}知识点，生成一道{dimension}维度的{q_type}题目，返回严格JSON（无markdown）：\n"
    if q_type == 'choice':
        prompt += '{"question":"...","options":[{"letter":"A","text":"..."},{"letter":"B","text":"..."},{"letter":"C","text":"..."},{"letter":"D","text":"..."}],"answer":"B","analysis":"..."}\n'
    elif q_type == 'judge':
        prompt += '{"question":"...","answer":"正确","analysis":"..."}\n'
    elif q_type == 'fill':
        prompt += '{"question":"...用____填空","answer":"...","analysis":"..."}\n'
    else:
        prompt += '{"question":"...","answer":"...","analysis":"..."}\n'
    prompt += f"知识点：{topic}\n内容：{content[:300]}"

    try:
        resp = requests.post(RELAY_URL, json={"message": prompt, "history": []}, timeout=130)
        reply = resp.json().get('reply', '')
        # Extract JSON
        start = reply.find('{')
        end = reply.rfind('}') + 1
        if start == -1 or end == 0:
            return None
        data = json.loads(reply[start:end])
        if not data.get('question'):
            return None
        return data
    except Exception as e:
        return None

def main():
    knowledge = question_generator.extract_all_knowledge()
    if not knowledge:
        print("[错误] 知识库为空"); return

    stats = database.get_stats()
    current = stats['total_questions']
    print(f"当前题库: {current} 题，目标: {TARGET}", flush=True)

    generated = 0
    failed = 0
    random.shuffle(knowledge)

    while current + generated < TARGET and failed < 100:
        for k in knowledge:
            if current + generated >= TARGET or failed >= 100:
                break
            q_type = random.choice(Q_TYPES)
            dim = random.choice(DIMENSIONS)
            diff = random.choice(DIFFICULTIES)
            topic = k.get('topic', '')
            content = k.get('content', '') or topic

            result = gen_one(topic, content, k['source'], k.get('chapter',''), q_type, dim, diff)
            if result:
                try:
                    database.add_question(
                        source=k['source'],
                        chapter=k.get('chapter',''),
                        topic=topic,
                        q_type=q_type,
                        question=result['question'],
                        answer=result.get('answer',''),
                        options=result.get('options'),
                        analysis=result.get('analysis',''),
                        difficulty=diff,
                        dimension=dim,
                        keywords=topic
                    )
                    generated += 1
                    if generated % 10 == 0:
                        print(f"[进度] {generated} 题 / 总计 {current+generated} 题", flush=True)
                except Exception as e:
                    print(f"[入库失败] {e}", flush=True)
            else:
                failed += 1
            time.sleep(0.3)

    final = database.get_stats()
    print(f"[完成] 生成 {generated} 题，最终 {final['total_questions']} 题", flush=True)

if __name__ == '__main__':
    main()
