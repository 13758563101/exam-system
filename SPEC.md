# 考试系统规格文档 (SPEC.md)

> 项目：云计算知识巩固考试系统
> 版本：1.0
> 更新：2026-04-09
> 负责人：贾维斯（AI助手）

---

## 1. 项目概述

### 1.1 目标
基于云计算五阶段知识库（Linux / MySQL / Shell / 高并发 / Docker&K8S），为炯哥提供智能化练习与考试系统，支持遗忘曲线复习和高质量 AI 出题。

### 1.2 核心价值
- **巩固知识**：通过反复练习强化长期记忆
- **精准复习**：遗忘曲线驱动，只练最需要复习的题
- **高质量出题**：AI 辅助生成高质量考题，覆盖命令/配置/原理/排错/实操五维度

---

## 2. 技术架构

```
用户浏览器 → Flask Web → exam.db (SQLite)
                            ↓
                     考试引擎 (Python)
                            ↓
                     知识库 (XMind) + 雷神 relay 出题
```

| 组件 | 技术 |
|------|------|
| 后端 | Python Flask |
| 数据库 | SQLite (exam.db) |
| 前端 | Jinja2 模板 |
| AI 出题 | 雷神 relay (Claude Code) |
| 知识库 | XMind 文件 + knowledge_search.py |
| 部署 | NAS (贾维斯实例) |

---

## 3. 数据库表结构

### question_bank（题库）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| source | TEXT | 来源模块（Linux/MySQL/Shell/高并发/K8S） |
| chapter | TEXT | 章节 |
| topic | TEXT | 知识点标签 |
| q_type | TEXT | 题型（choice/fill/judge/short_answer/operation） |
| difficulty | INTEGER | 难度 1-5 |
| dimension | TEXT | 维度（命令/配置/原理/排错/实操） |
| question | TEXT | 题目正文 |
| answer | TEXT | 答案 |
| analysis | TEXT | 解析 |
| keywords | TEXT | 关键词，逗号分隔 |
| created_at | TIMESTAMP | 创建时间 |
| used_count | INTEGER | 使用次数 |
| correct_rate | REAL | 历史正确率 |

### wrong_answers（错题库 + 遗忘曲线）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| q_id | INTEGER | 关联题库ID |
| wrong_count | INTEGER | 错误次数 |
| last_wrong_at | TIMESTAMP | 上次错误时间 |
| next_review_at | TIMESTAMP | 下次复习时间 |
| mastery_level | REAL | 掌握度 0.0-1.0 |
| review_interval | INTEGER | 当前间隔天数 |
| wrong_history | TEXT | JSON 历史记录 |

### exam_records（考试记录）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| exam_type | TEXT | 考试类型（daily/chapter/comprehensive） |
| source | TEXT | 涉及模块 |
| total_count | INTEGER | 总题数 |
| correct_count | INTEGER | 正确数 |
| score | REAL | 百分制分数 |
| wrong_ids | TEXT | 错题ID列表 JSON |
| created_at | TIMESTAMP | 考试时间 |

---

## 4. 功能模块

### 4.1 每日一练（Daily Practice）
- **触发**：手动或定时（早8点随简报）
- **题量**：10道
- **组卷**：60% 错题库（遗忘曲线排序）+ 40% 新题
- **模块轮换**：五阶段按序轮换

### 4.2 章节练习（Chapter Practice）
- 按模块/章节选择
- 题量可选：10/20/30/50
- 可选考核维度
- 不限时间

### 4.3 综合考试（Comprehensive Exam）
- 题量：30/50/100 可选
- 多模块混合
- 计时功能

### 4.4 错题库（Wrong Answers）
- 查看所有错题及历史
- 显示：错误次数、掌握度、复习历史
- 手动标记"已掌握"
- 雷神协助分析错因

### 4.5 遗忘曲线调度
基于 SM-2 改良算法：
```
首次错误 → 1天后复习
再次错误 → 3天后复习
再次错误 → 7天后复习
再次错误 → 14天后复习
连续正确2次 → 掌握度+0.2
掌握度 >= 0.9 → 降低出现频率
```

---

## 5. 题型说明

| 题型 | 说明 | 示例 |
|------|------|------|
| choice | 单选/多选 | crontab 第三个 * 代表什么 |
| fill | 填空题 | systemctl start ____ |
| judge | 判断题 | MySQL 乐观锁适合高并发写场景 |
| short_answer | 简答题 | Docker 与虚拟机的核心区别 |
| operation | 操作题 | 写一个 Nginx 反向代理配置 |

---

## 6. 考核维度

| 维度 | 考核目标 |
|------|---------|
| 命令 | 命令语法、参数、适用场景 |
| 配置 | 配置文件格式、参数调优 |
| 原理 | 工作机制、核心概念 |
| 排错 | 故障诊断、问题定位 |
| 实操 | 完整操作步骤、脚本编写 |

---

## 7. 界面说明

### 答题页
- 题目 + 选项（选择题按钮形式）
- 填空题/操作题文本框
- **[查看答案]** 按钮（点击展开答案+解析）
- 提交按钮 → 即时反馈 ✅/❌

### 答题结果页
- 得分 + 用时
- 错题列表（可点击查看详情）
- 薄弱知识点提示

---

## 8. 交付标准

- [x] 每日一练可手动触发，10道题
- [x] 每道题可隐藏/展开答案+解析
- [x] 错题自动入库，按遗忘曲线出现在后续试卷中
- [x] 雷神协助生成高质量考题
- [x] 可按模块/章节/维度筛选练习
- [x] 历史成绩可查
- [ ] 综合考试计时功能
- [ ] 掌握度热力图
- [ ] 微信/QQ 推送集成

---

## 9. 禁止事项（Red Lines）

- 不得修改数据库字段结构而不更新 SPEC.md
- 新功能未写测试不得合入 main 分支
- 每次发布必须更新 CHANGELOG.md

---

## 10. 维护规则

| 操作 | 更新文档 |
|------|---------|
| 新增题型/功能 | 更新 SPEC.md + CHANGELOG.md |
| 技术决策 | 追加 DECISIONS.md |
| Bug 发现 | GitHub Issue |
| 代码大改 | 更新 CONTRIBUTING.md |

---

*本文档是考试系统的唯一真实规格源。每次修改代码前先更新本文档。*
