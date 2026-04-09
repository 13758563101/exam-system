#!/usr/bin/env python3
"""Flask 考试应用"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
import database, exam_engine
from flask import (Flask, render_template, request, redirect, url_for, jsonify, session, flash)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'exam-secret-key-change-in-production')
database.init_db()


@app.route('/')
def index():
    stats = database.get_stats()
    return render_template('index.html', stats=stats)


@app.route('/exam/<exam_type>')
def start_exam(exam_type):

    n = request.args.get('n', type=int) or 80
    n = min(n, 100)

    if exam_type == 'daily':
        questions, source = exam_engine.generate_daily_exam(n=n)
    elif exam_type == 'chapter':
        source = request.args.get('source', 'Linux')
        questions = exam_engine.generate_chapter_exam(source=source, n=n)
    elif exam_type == 'comprehensive':
        questions, source = exam_engine.generate_comprehensive_exam(n=n)
    else:
        return redirect(url_for('index'))

    if not questions:
        flash('题库暂无题目，请先导入题目！')
        return redirect(url_for('index'))

    # 清理旧会话数据，防止进度残留
    for key in list(session.keys()):
        session.pop(key, None)
    session['exam_type'] = exam_type
    session['learn_mode'] = request.args.get('learn', '1') == '1'
    session['source'] = source
    session['questions'] = [q['id'] for q in questions]
    total_score = sum(q.get('score', 10) for q in questions)

    for q in questions:
        if isinstance(q.get('options'), str):
            try:
                q['options'] = json.loads(q['options'])
            except Exception:
                q['options'] = []

    return render_template('exam.html',
                           questions=questions,
                           exam_type=exam_type,
                           source=source,
                           total_score=total_score,
                           learn_mode=session['learn_mode'])


@app.route('/submit', methods=['POST'])
def submit_exam():
    exam_type = session.get('exam_type', 'daily')
    source = session.get('source', '')
    question_ids = session.get('questions', [])
    learn_mode = session.pop('learn_mode', False)

    questions = []
    for qid in question_ids:
        q = database.get_question(qid)
        if q:
            if isinstance(q.get('options'), str):
                try:
                    q['options'] = json.loads(q['options'])
                except Exception:
                    q['options'] = []
            questions.append(q)

    answers = {k: v for k, v in request.form.items() if k.startswith('q')}
    session['user_answers'] = answers
    correct, wrong_count, wrong_ids, score = exam_engine.grade_exam(questions, answers)

    rid = exam_engine.save_exam_record(
        exam_type=exam_type, source=source,
        questions=questions, correct=correct,
        wrong_ids=wrong_ids, score=score
    )
    # 不清理 session，result 页面需要用到
    return redirect(url_for('result', record_id=rid))


@app.route('/result/<int:record_id>')
def result(record_id):
    record = database.get_exam_record(record_id)
    if not record:
        flash('考试记录不存在')
        return redirect(url_for('index'))

    wrong_ids = []
    try:
        wrong_ids = json.loads(record.get('wrong_ids', '[]'))
    except Exception:
        pass

    weak_chapters = database.get_weak_chapters(wrong_ids, limit=3)

    wrong_questions = []
    for qid in wrong_ids:
        q = database.get_question(qid)
        if q:
            if isinstance(q.get('options'), str):
                try:
                    q['options'] = json.loads(q['options'])
                except Exception:
                    q['options'] = []
            wrong_questions.append(q)

    user_answers = session.get('user_answers', {})
    return render_template('result.html',
                           record=record,
                           wrong_questions=wrong_questions,
                           weak_chapters=weak_chapters,
                           user_answers=user_answers)


@app.route('/wrong_bank')
def wrong_bank_page():
    return render_template('wrong_bank.html')


@app.route('/api/wrong_bank')
def api_wrong_bank():
    limit = request.args.get('limit', 50, type=int)
    wrong_list = database.get_wrong_bank(limit=limit)
    for q in wrong_list:
        if isinstance(q.get('options'), str):
            try:
                q['options'] = json.loads(q['options'])
            except Exception:
                q['options'] = []
    return jsonify(wrong_list)


@app.route('/api/wrong/<int:qid>/master', methods=['POST'])
def api_mark_master(qid):
    database.mark_as_master(qid)
    return jsonify({'success': True, 'qid': qid})


# === 新增路由 ===

@app.route('/profile')
def profile_page():
    stats = database.get_user_stats(days=30)
    return render_template('profile.html', stats=stats)


@app.route('/api/stats')
def api_stats():
    days = request.args.get('days', 30, type=int)
    stats = database.get_user_stats(days=days)
    return jsonify(stats)


@app.route('/favorites')
def favorites_page():
    favs = database.get_favorites(limit=200)
    for q in favs:
        if isinstance(q.get('options'), str):
            try:
                q['options'] = json.loads(q['options'])
            except Exception:
                q['options'] = []
    return render_template('favorites.html', questions=favs)


@app.route('/api/favorites', methods=['GET'])
def api_get_favorites():
    favs = database.get_favorites(limit=200)
    return jsonify({'success': True, 'data': favs, 'count': len(favs)})


@app.route('/api/favorites/<int:qid>', methods=['POST'])
def api_add_favorite(qid):
    added = database.add_favorite(qid)
    return jsonify({'success': added, 'action': 'added' if added else 'exists'})


@app.route('/api/favorites/<int:qid>', methods=['DELETE'])
def api_remove_favorite(qid):
    removed = database.remove_favorite(qid)
    return jsonify({'success': removed})


if __name__ == '__main__':
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        import scheduler
        sched = BackgroundScheduler()
        # 每天9点 - 遗忘曲线提醒
        sched.add_job(func=scheduler.check_and_remind, trigger='cron', hour=9, minute=0)
        # 每周日22点 - 自动批量入库
        sched.add_job(func=scheduler.weekly_import, trigger='cron', day_of_week='sun', hour=22, minute=0)
        sched.start()
        print("[Scheduler] 定时任务已启动（每天9:00遗忘提醒 + 周日22:00自动入库）")
    except Exception as e:
        print(f"[Scheduler] 启动失败: {e}")

    port = int(os.environ.get('PORT', 7758))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
