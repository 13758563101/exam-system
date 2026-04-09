# 开发规范 (CONTRIBUTING.md)

---

## 分支命名

| 类型 | 格式 | 示例 |
|------|------|------|
| 功能 | `feature/xx` | `feature/multi-choice` |
| 修复 | `fix/xx` | `fix/wrong-answer-sort` |
| 重构 | `refactor/xx` | `refactor/db-schema` |
| 文档 | `docs/xx` | `docs/add-api-doc` |

---

## Commit 规范

```
<类型>: <简短描述>

示例：
feat: 添加多选题支持
fix: 修复选择题重复提交问题
docs: 更新 SPEC.md 题型说明
refactor: 重构考试引擎抽取逻辑
test: 添加每日一练单元测试
```

---

## PR 流程（必须遵守）

```
1. 从 dev 分支创建 feature/xx 分支
2. 完成开发 + 自测
3. 提 PR 到 dev 分支
4. 雷神 relay review（score ≥ 8）
5. Sir 验收
6. 合并到 dev
7. dev 稳定后合并到 main
```

---

## 代码规范

- **Python**：PEP 8，使用 `flake8` 检查
- **SQL**：关键字大写 `SELECT * FROM`
- **变量命名**：下划线分隔 `wrong_count`
- **函数命名**：`verb_noun` 形式 `get_next_review()`

---

## 测试要求

- 新功能必须有对应测试（pytest）
- 测试覆盖率 ≥ 70%
- PR 前跑 `pytest tests/` 必须全通过
- 数据库相关测试用 mock，不碰真实数据库

---

## 数据库修改规范

任何表结构变更必须：
1. 先更新 `SPEC.md` 数据表结构
2. 写数据迁移脚本（`migrations/` 目录）
3. 测试迁移脚本可逆
4. 更新 `DECISIONS.md`（如涉及技术变更）

---

## 评审清单（Review Checklist）

PR 合入前检查：
- [ ] 功能符合 SPEC.md 吗？
- [ ] 有没有明显的 bug？
- [ ] 新代码破坏原有功能了吗？
- [ ] 测试写了吗？跑过了吗？
- [ ] 文档更新了吗（SPEC.md / CHANGELOG.md）？
- [ ] commit message 规范吗？
- [ ] 代码风格符合规范吗？
