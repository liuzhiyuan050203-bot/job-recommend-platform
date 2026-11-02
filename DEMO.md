# 系统演示检查清单

面向答辩 / 验收的 5 分钟路径。先执行 `bash scripts/start-all.sh`，浏览器打开 http://localhost:5173 ，也可打开 http://localhost:5173/demo 。

## 演示账号

| 角色 | 用户名 | 密码 |
| :--- | :--- | :--- |
| 管理员 | admin | admin123 |
| 学生 | student | student123 |
| 企业 | company | company123 |

登录页可点「填入管理员 / 学生 / 企业」，或访问 `/login?demo=student`。

## 学生路径

- [ ] 登录 student
- [ ] 「求职看板」：投递状态饼图、技能雷达、薪资预测、推荐摘要有数据
- [ ] 「职位」浏览并投递一个未投过的职位
- [ ] 「为你推荐」列表有匹配分与理由
- [ ] 「就业助手」提问：例如「杭州后端实习大概什么薪资？」（需 Ollama/LLM，CPU 约数十秒）

## 企业路径

- [ ] 登录 company（星澜科技，资质已通过）
- [ ] 「招聘看板」：职位浏览/收藏/投递、投递漏斗、候选人技能柱状图
- [ ] 「候选人」将一条投递推进状态（笔试/面试等）
- [ ] 「招聘助手」提问：例如「帮我看看怎么筛选后端实习生」

## 管理员路径

- [ ] 登录 admin
- [ ] 「数据分析」：概览卡片、城市薪资、技术趋势、地区分布；下方推荐指标与 AI 会话/消息数
- [ ] 「推荐评估」查看 NDCG 等离线指标
- [ ] （可选）运行 Spark 分析 / 推荐任务
- [ ] 「知识库」与「数据助手」抽查

## 公开首页

- [ ] `/` 概览卡片（职位/企业/学生/投递）与真实图表（非「静态演示」）
- [ ] `/demo` 系统演示指南三条路径可点

## 一键启停

```bash
bash scripts/start-all.sh          # MySQL 8.4 + Ollama + ai-service + 后端 + 前端
bash scripts/stop-all.sh           # 停应用，默认保留 MySQL
```

健康检查：`curl -s http://localhost:8080/api/health`

## 接口冒烟（可选）

```bash
bash tests/api/07-dashboard.sh     # 需后端已启动
bash tests/run-all.sh              # 全量 API
```
