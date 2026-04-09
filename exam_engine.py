"""考试引擎 - 组卷与判分"""
import re
import random
from datetime import datetime
from typing import List, Dict, Tuple
import database

DIFFICULTY_SCORE = {1: 5, 2: 8, 3: 10, 4: 12}
DEFAULT_SCORE = 10

def diff_to_score(difficulty):
    return DIFFICULTY_SCORE.get(difficulty, DEFAULT_SCORE)

# 默认80题分配
DEFAULT_TYPE_MIX = {
    'choice': {'count': 35, 'score_range': (5, 10)},
    'judge': {'count': 20, 'score_range': (5, 5)},
    'fill': {'count': 15, 'score_range': (5, 10)},
    'short_answer': {'count': 10, 'score_range': (8, 12)},
}
# 100题分配
LARGE_TYPE_MIX = {
    'choice': {'count': 40, 'score_range': (5, 10)},
    'judge': {'count': 25, 'score_range': (5, 5)},
    'fill': {'count': 20, 'score_range': (5, 10)},
    'short_answer': {'count': 15, 'score_range': (8, 12)},
}


def get_weekday_source() -> str:
    sources = ['Linux', 'MySQL', 'Shell', '高并发', 'K8S']
    return sources[datetime.now().weekday() % len(sources)]


def normalize_answer(user_answer: str) -> str:
    return re.sub(r'[\s，。、；;:（）()""\'\'《》【】\[\]]', '', user_answer.strip().lower())


def _normalize_scores(questions, target=100):
    """将题目分值归一化，确保总分=target。归一化前备份原始difficulty分，判分时用原始值。"""
    if not questions:
        return questions
    raw_total = sum(q.get('_raw_score', q.get('score', 10)) for q in questions)
    if raw_total == 0:
        return questions
    for q in questions:
        raw = q.get('_raw_score', q.get('score', 10))
        q['score'] = round(raw / raw_total * target, 2)
    return questions


def _backup_raw_scores(questions):
    """备份每题的原始 difficulty 分值到 _raw_score，避免归一化后无法恢复"""
    for q in questions:
        q['_raw_score'] = q.get('score', 10)
    return questions


def generate_comprehensive_exam(n=80) -> Tuple[List[Dict], str]:
    """综合考试 - 按题型+模块比例组卷，薄弱优先"""
    type_mix = DEFAULT_TYPE_MIX if n == 80 else LARGE_TYPE_MIX
    source_weights = {
        'Linux': 0.38,
        '高并发': 0.29,
        'MySQL': 0.14,
        'Shell': 0.12,
        'K8S': 0.07,
    }

    result = []
    used_ids = []

    for q_type, config in type_mix.items():
        count = config['count']
        for src, weight in source_weights.items():
            src_count = max(1, int(count * weight))
            # 60%从错题库
            wrong = database.get_wrong_bank(limit=src_count, q_types=[q_type])
            wrong_ids = [q['id'] for q in wrong if q['id'] not in used_ids]
            for wid in wrong_ids[:int(src_count * 0.6)]:
                q = database.get_question(wid)
                if q:
                    q['score'] = q.get('score') or diff_to_score(q.get('difficulty', 3))
                    result.append(q)
                    used_ids.append(wid)
            # 40%从新题
            new_count = src_count - len([w for w in wrong if w['id'] in used_ids])
            new_qs = database.get_random_questions(
                source=src, q_types=[q_type],
                exclude_ids=used_ids, limit=max(0, new_count)
            )
            for q in new_qs:
                q['score'] = q.get('score') or diff_to_score(q.get('difficulty', 3))
                result.append(q)
                used_ids.append(q['id'])

    random.shuffle(result)
    # 不够则补新题
    if len(result) < n:
        more = database.get_random_questions(exclude_ids=used_ids, limit=n - len(result))
        for q in more:
            q['score'] = q.get('score') or diff_to_score(q.get('difficulty', 3))
            result.append(q)

    _backup_raw_scores(result)
    result = _normalize_scores(result[:n])
    return result, '综合'


def generate_daily_exam(n=80) -> Tuple[List[Dict], str]:
    """每日一练 - 按周轮换模块，60%错题+40%新题"""
    daily_source = get_weekday_source()
    wrong_bank = database.get_wrong_bank(limit=n)
    wrong_ids = [q['id'] for q in wrong_bank]
    wrong_ids_set = set(wrong_ids)
    new_needed = n - len(wrong_bank)

    from_wrong = wrong_bank[:int(n * 0.6)]
    for q in from_wrong:
        q['score'] = q.get('score') or diff_to_score(q.get('difficulty', 3))

    from_new = database.get_random_questions(
        source=daily_source, exclude_ids=wrong_ids, limit=new_needed
    )
    if len(from_new) < new_needed:
        more = database.get_random_questions(
            exclude_ids=wrong_ids + [q['id'] for q in from_new],
            limit=new_needed - len(from_new)
        )
        from_new.extend(more)

    for q in from_new:
        q['score'] = q.get('score') or diff_to_score(q.get('difficulty', 3))

    questions = from_wrong + from_new
    random.shuffle(questions)
    _backup_raw_scores(questions)
    questions = _normalize_scores(questions)
    return questions, daily_source


def generate_chapter_exam(source: str, n=80) -> List[Dict]:
    """章节练习 - 指定模块80题"""
    questions = database.get_random_questions(source=source, limit=n)
    for q in questions:
        q['score'] = q.get('score') or diff_to_score(q.get('difficulty', 3))
    return questions


def grade_exam(questions: List[Dict], answers: Dict) -> Tuple[int, int, List[int], float]:
    """
    判分 - 用原始 difficulty 分值计算，不受归一化影响
    返回: (correct_count, wrong_count, wrong_ids, score)
    score: 0-100
    """
    correct = 0
    wrong_ids = []
    total_score = 0
    earned_score = 0

    for q in questions:
        qid = q['id']
        # 优先用 _raw_score（归一化前备份），其次用 difficulty 计算，fallback 到 score 字段
        score = q.get('_raw_score') or diff_to_score(q.get('difficulty', 3))
        total_score += score
        user_answer = normalize_answer(answers.get(f'q{qid}', ''))
        correct_answer = normalize_answer(str(q['answer']))
        is_correct = user_answer == correct_answer

        if is_correct:
            correct += 1
            earned_score += score
            database.update_question_stats(qid, True)
        else:
            wrong_ids.append(qid)
            database.upsert_wrong_answer(qid, user_answer=user_answer, is_correct=False)
            database.update_question_stats(qid, False)

    score = round(earned_score / total_score * 100, 1) if total_score > 0 else 0.0
    return correct, len(wrong_ids), wrong_ids, score


def save_exam_record(exam_type: str, source: str,
                     questions: List[Dict], correct: int,
                     wrong_ids: List[int], score: float) -> int:
    total = len(questions)
    return database.add_exam_record(
        exam_type=exam_type, source=source,
        total_count=total, correct_count=correct,
        score=score, wrong_ids=wrong_ids
    )
