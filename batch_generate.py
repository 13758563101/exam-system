#!/usr/bin/env python3
"""快速批量生成题目 - 每次 relay 调用生成多道题"""
import sys, os, json, random, time
sys.path.insert(0, '/vol1/@apphome/trim.openclaw/data/workspace/exam-system')

import question_generator
import relay_client
import database

Q_TYPES = ['choice', 'judge', 'fill', 'short_answer']
DIMENSIONS = ['命令', '配置', '原理', '排错']
DIFFICULTIES = [2, 3, 3, 4, 4]
TARGET_PER_MODULE = 40


def generate_multi(knowledge_list, count=5):
    """一次 relay 调用生成多道题"""
    selected = random.sample(knowledge_list, min(count, len(knowledge_list)))
    
    items = []
    for i, k in enumerate(selected):
        q_type = random.choice(Q_TYPES)
        dim = random.choice(DIMENSIONS)
        topic = k.get('topic', '')
        content = k.get('content', topic)[:200]
        items.append({
            'index': i + 1,
            'q_type': q_type,
            'dimension': dim,
            'topic': topic,
            'content': content,
            'source': k['source'],
            'chapter': k['chapter'],
        })
    
    prompt = (
        '你是云计算课程题目生成专家。请根据以下知识点生成多道不同题型的题目。'
        '返回严格JSON数组格式（无markdown代码块）：\n'
        '[{"question":"题目","options":[...],"answer":"答案","analysis":"解析","q_type":"choice/dedent"},...]\n\n'
        '知识点列表：\n'
    )
    for item in items:
        prompt += f"[{item['index']}] 知识点：{item['topic']}，模块：{item['source']}，章节：{item['chapter']}，题型：{item['q_type']}，维度：{item['dimension']}\n"
    prompt += '\n题型规则：choice 题型 options 必须是有4个选项的数组。'
    
    try:
        resp = relay_client.requests_post_relay(prompt, language="Chinese", timeout=180)
        questions = relay_client.get_client().parse_multi_questions(resp)
        
        results = []
        for i, q in enumerate(questions):
            if i < len(items) and q.get('question'):
                item = items[i]
                results.append({
                    'question': q['question'],
                    'options': q.get('options'),
                    'answer': q.get('answer', ''),
                    'analysis': q.get('analysis', ''),
                    'q_type': item['q_type'],
                    'dimension': item['dimension'],
                    'source': item['source'],
                    'chapter': item['chapter'],
                    'topic': item['topic'],
                    'difficulty': random.choice(DIFFICULTIES),
                })
        return results, items
    except Exception as e:
        print(f"[批量生成失败] {e}", flush=True)
        return [], items


def main():
    print("[快速批量生成] 开始...", flush=True)
    knowledge = question_generator.extract_all_knowledge()
    if not knowledge:
        print("知识库为空！", flush=True)
        return

    from collections import defaultdict
    by_source = defaultdict(list)
    for k in knowledge:
        by_source[k['source']].append(k)
    for src in by_source:
        random.shuffle(by_source[src])

    conn = database.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT source, COUNT(*) FROM question_bank GROUP BY source")
    current = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()
    
    total_now = sum(current.values())
    print(f"当前题库：{total_now} 题 {dict(current)}", flush=True)

    target_modules = ['Linux', 'MySQL', 'Shell', '高并发', 'K8S']
    generated = 0
    batch_num = 0
    
    while True:
        all_done = all(current.get(src, 0) >= TARGET_PER_MODULE for src in target_modules)
        if all_done:
            break
        
        # 收集未达标模块的知识
        pending = []
        for src in target_modules:
            if current.get(src, 0) < TARGET_PER_MODULE:
                needed = TARGET_PER_MODULE - current.get(src, 0)
                avail = by_source[src][:needed * 2]  # 多取一些
                pending.extend(avail)
        
        if not pending:
            break
        
        batch_num += 1
        print(f"\n[批次 {batch_num}] 生成中... ({len(pending)} 个知识点待处理)", flush=True)
        
        # 每次调用生成 5 道题
        questions = []
        for i in range(0, min(len(pending), 20), 5):
            batch_k = pending[i:i+5]
            qs, items = generate_multi(batch_k, count=len(batch_k))
            questions.extend(qs)
            print(f"  本批次返回 {len(qs)} 道题", flush=True)
            time.sleep(0.5)
        
        if not questions:
            print("[警告] 本批次生成失败，等待后重试...", flush=True)
            time.sleep(10)
            continue
        
        # 入库
        for q in questions:
            if current.get(q['source'], 0) >= TARGET_PER_MODULE:
                continue
            try:
                qid = database.add_question(
                    source=q['source'],
                    chapter=q.get('chapter', ''),
                    topic=q.get('topic', ''),
                    q_type=q.get('q_type', 'choice'),
                    question=q['question'],
                    answer=q.get('answer', ''),
                    options=q.get('options'),
                    analysis=q.get('analysis', ''),
                    difficulty=q.get('difficulty', 3),
                    dimension=q.get('dimension'),
                    keywords=q.get('topic', '')
                )
                if qid:
                    generated += 1
                    current[q['source']] = current.get(q['source'], 0) + 1
            except Exception as e:
                print(f"[入库失败] {e}", flush=True)
        
        print(f"[进度] 已生成 {generated} 题 | {dict(current)}", flush=True)

    stats = database.get_stats()
    print(f"\n[完成] 共生成 {generated} 道新题目！", flush=True)
    print(f"题库总计：{stats['total_questions']} 题", flush=True)
    
    conn = database.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT source, COUNT(*) FROM question_bank GROUP BY source ORDER BY source")
    for r in cur.fetchall():
        status = "✅" if r[1] >= TARGET_PER_MODULE else "❌"
        print(f"  {status} {r[0]}: {r[1]} 题", flush=True)
    conn.close()


if __name__ == '__main__':
    main()
