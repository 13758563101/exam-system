# 云计算考试系统

> 基于遗忘曲线 + AI 出题的知识巩固系统

---

## 功能

- 📅 **每日一练** — 10道题，60% 错题库 + 40% 新题
- 📚 **章节练习** — 按模块/章节/维度筛选
- 🎯 **综合考试** — 30/50/100题，计时考试
- ❌ **错题库** — 遗忘曲线驱动，只练最需要复习的
- 🤖 **AI 出题** — 雷神 relay 生成高质量考题
- 📊 **学习报告** — 掌握度热力图（规划中）

---

## 快速开始

```bash
# 启动服务
cd /path/to/exam-system
python3 app.py

# 访问
http://localhost:5000
```

---

## 项目结构

```
exam-system/
├── app.py              # Flask 入口
├── exam_engine.py      # 考试引擎核心
├── database.py         # 数据库操作
├── question_generator.py # 题库生成
├── relay_client.py     # 雷神 relay 客户端
├── scheduler.py        # 定时调度
├── exam.db             # SQLite 数据库
├── templates/          # HTML 模板
└── static/             # CSS/JS
```

---

## 技术栈

- **后端**：Python Flask
- **数据库**：SQLite
- **前端**：Jinja2 + 原生 JS
- **AI**：Claude Code (雷神 relay)
- **知识库**：云计算五阶段 XMind

---

## 开发

```bash
# 安装依赖
pip install flask

# 运行测试
pytest tests/

# 代码检查
flake8 app.py exam_engine.py
```

---

## 文档

- [SPEC.md](SPEC.md) — 完整规格文档
- [CHANGELOG.md](CHANGELOG.md) — 变更日志
- [DECISIONS.md](DECISIONS.md) — 技术决策记录
- [CONTRIBUTING.md](CONTRIBUTING.md) — 开发规范
