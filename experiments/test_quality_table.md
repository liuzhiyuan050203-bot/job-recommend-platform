# 接口测试质量表（真实 run-all）

- 时间（Asia/Shanghai）：2026-11-01 10:55:58 
- 命令：`bash tests/run-all.sh`
- 合计：**PASS=661 FAIL=0**（exit 0）
- 日志：`/workspace/bishe-logs/rigor/run_all_final.log`

| 脚本 | PASS | FAIL | 覆盖要点 |
|------|-----:|-----:|----------|
| `01-auth.sh` | 35 | 0 | 登录/注册/401/403/改密 |
| `02-module1.sh` | 165 | 0 | 职位检索、收藏、投递、社区等主业务 |
| `03-recruitment.sh` | 89 | 0 | 企业发岗/审核/投递流 |
| `04-spark.sh` | 55 | 0 | 清洗/聚合/薪资预测/stats（真实 pooled RF） |
| `05-recommend.sh` | 51 | 0 | 推荐接口与冷启动 |
| `06-rag.sh` | 92 | 0 | 知识库检索/问答（含 hybrid） |
| `07-dashboard.sh` | 49 | 0 | 管理端与企业看板 |
| `08-security.sh` | 77 | 0 | IDOR/越权/JWT 相关 |
| `09-resume.sh` | 48 | 0 | PDF/DOCX 解析→技能→推荐 |
| **合计** | **661** | **0** | |

`mvn -DskipTests package` 与 `pnpm build` 本轮均成功。生产 Spark 管线未改为 Pandas。

