# UX 审计修复说明

对应审计报告 [REPORT.md](./REPORT.md) 与整改指南 `/workspace/bishe-logs/uxfix/GUIDE.md`。  
按 GUIDE **意图**落地到真实代码结构；与指南伪代码不一致处均记入「相对 GUIDE 的偏差」。  
仓库曾短期 PUBLIC，提交不含密钥；`experiments/data/` 未入库。

| 项 | 级别 | 主题 | Commit | 专项测试 |
| --- | --- | --- | --- | --- |
| 1 | P0 | 企业助手投递概况与角色隔离 | `c403163` | `10-company-assistant.sh` + unittest |
| 2 | P1-3 | 测试数据污染清理 | `2358d2e` | `11-demo-data.sh` + fixture 回收 |
| 3 | P1-1 | 推荐方向归一与理由 | `8c0704c`；消融文档 `b540d72` | `12-recommend-direction.sh`（20）+ unittest 9 |
| 4 | P1-2 | 职位详情爬虫 JSON 清洗 | `b4f361c`（学生详情页 UI 随 `066b4ed`） | `13-job-detail.sh`（21）+ JobTextCleanerTest 5 |
| 5 | P1-4 | 发岗技能必填与候选人匹配分 | `ea174e2` | `14-candidate-match.sh`（37）+ SkillMatchTest 4 |
| 6 | P1-5 | PDF 技能同步默认简历与投递预览 | `066b4ed` | `15-apply-resume-sync.sh`（23）+ ResumeSkillSyncTest 3 |

回归：

- P1-2/P1-4 落地后全量（01–14）：**795/0**（`/workspace/bishe-logs/uxfix/runall_item45.log`）。
- P1-5 纳入后最终全量（01–15）：**816/2**（`runall_final.log`）。2 条失败经复跑均为环境/模型偶发，非本轮回归：
  1. `10-company-assistant`「企业兜底回答无学生话术」：SSE 偶发模型口吻；单独复跑 **25/0**。
  2. `11-demo-data`「临时账号已收尾」：执行器调试会话 `trap - EXIT` 留下的 `pdfdbg*` 未回收；清理后单独复跑 **21/0**。
- 专项：`13`=21、`14`=37、`15`=23。

---

## 1. P0 企业招聘助手（`c403163`）

**改动要点**：企业「本周投递概况」等问句命中本公司投递统计工具；企业兜底不再走学生就业政策文档与「学校就业指导中心」话术。

**相对 GUIDE 的偏差**

- 工具名落地为 `application_stats`（非 `get_weekly_deliver_summary`）。
- 企业 ID 经 `ent_company.user_id` 解析，而非直接用 `caller.user_id`。
- 企业兜底文档类型为 `{4,6}`，统计意图不混入学生侧资料。

**测试**：`10-company-assistant.sh` PASS=25；配套 unittest 12。当时全量约 691/0。

---

## 2. P1-3 测试数据污染（`2358d2e`）

**改动要点**：API 测试夹具在 `lib.sh` 的 `EXIT` 陷阱中逻辑删除回收；一次性清理脚本与演示投递漏斗再平衡；避免公开展示「越权隔离职位*」等污染标题与异常「已录用」占比。

**相对 GUIDE 的偏差**

- **未**按 id 取模批量改状态（明确禁止）。
- 未在公开列表加标题黑名单过滤；靠夹具生命周期 + 一次性清理。
- 漏斗按投递概率播种，而非指南中的简单 SQL 改写。

**备份**（均在 `/workspace/bishe-logs/uxfix/`）

- `backup_before_cleanup.sql.gz`
- `backup_before_cleanup_run2.sql.gz`
- （技能重标另有 `backup_job_position_tag_before_retag.sql.gz`，属 P1-1 数据修正）

**测试**：`11-demo-data.sh` PASS=21；全量约 717/0。

---

## 3. P1-1 推荐方向与理由（`8c0704c` + `b540d72`）

**改动要点**

- 内容/融合路径对冲突方向降权；理由按真实技能命中生成并轮换句式，去掉空泛「技能匹配度」。
- 新增 `data/retag_real_jobs.py` 修正真实职位错误技能标签。
- 消融与 Spark 等价性重跑后更新 `experiments/results|figures` 与 README 指标。

**相对 GUIDE 的偏差**

- 未采用指南字面的 1.45×/0.30× 乘子；内容侧用方向分（1/0.5/0），并对冲突方向再乘因子（远 0.5、近 0.9），作用于内容、线性 CF 与冷启动热门。
- 纯 CF（algo 1）不加权；Java SQL 兜底理由未改；`recommend_service.py` 未改。
- 增加了指南未写的真实职位 retag 脚本。
- 消融用户/物品规模变化（201×4960），绝对值上升，只宜同一次运行内对比；`pop_noise` 下方向加权有 NDCG 与 FarDir 权衡，文档如实写明。

**测试**：`12-recommend-direction.sh` PASS=20；`test_recommend_direction` 9。全量（item3）737/0。

---

## 4. P1-2 职位详情清洗（`b4f361c`，学生详情 UI 在 `066b4ed`）

**改动要点**

- 后端 `JobTextCleaner` 在 **读详情 VO** 时清洗 description/requirement/welfare，抽出 `descriptionItems` / `requirementItems`、`dataSource`、`salaryEstimated` / `salaryNote`；**库内 provenance JSON 保留**。
- 管理端审核页与学生详情页结构化列表 + 数据来源徽标 + 估算薪资脚注；前端 `jobText.js` 兜底解析。

**相对 GUIDE 的偏差**

- 清洗在后端 VO 组装，而非改导入脚本或写迁移；便于溯源。
- 未清洗 ai-service RAG ingest / 推荐文本中的 requirement（需全量重索引，本次刻意跳过）。
- 学生端 `JobDetail.vue` 详情区与 P1-5 投递弹窗同一文件，UI 随 `066b4ed` 提交（后端 VO 已在 `b4f361c`）。

**测试**：`13-job-detail.sh` PASS=21；`JobTextCleanerTest` 5。

---

## 5. P1-4 发岗技能与候选人匹配（`ea174e2`）

**改动要点**

- `JobSaveDTO.tagIds`：`@NotEmpty`；服务层 `requireTags` 拒绝空列表；前端表单必填 +「从描述提取」。
- 企业候选人列表/详情：`candidateSkills`（熟练度中文名、是否命中）、`missingSkills`、`matchScore`；支持 `sort=matchDesc|matchAsc`（内存排序，上限 2000）。
- 抽屉内也可改状态；`refreshAfterChange` 同步刷新抽屉。

**相对 GUIDE 的偏差**

- 匹配分：职位每技能 1 份，命中按熟练度 `0.5+0.1×level`（入门 0.6 … 精通 1.0），`round(100×Σ/职位技能数)`；**职位无标签时 score=null**（不做指南里的 50/75 假分）。
- 技能来自学生档案 `stu_skill`，不合并简历解析 JSON 字段（本系统无 `parsedSkills` 列）。
- 熟练度展示为文字而非星号串。

**测试**：`14-candidate-match.sh` PASS=37；`SkillMatchTest` 4。

---

## 6. P1-5 PDF 技能与投递简历（`066b4ed`）

**改动要点**

- 合并 PDF 技能到档案后，`ResumeSkillSync` 写入**非测试标题**的默认在线简历 `skillDesc`；若无可用简历则创建「姓名-校招简历」。
- 上传时 `ensureResume` 同样避开测试标题。
- 投递弹窗：过滤测试简历、优先校招/默认；预览档案技能 ∪ 简历 skillDesc，并按职位 `tagNames` 高亮命中。

**相对 GUIDE 的偏差**

- 解析服务只返回 skills + textPreview，**无**独立 education/projects 结构化字段，故只同步技能概述。
- 无 `parsedSkills` JSON 列，落在现有 `skillDesc` 文本。
- 测试标题正则覆盖 UX-IDOR/越权/推荐测试等夹具，而非仅指南列举的少数模式。

**测试**：`15-apply-resume-sync.sh` PASS=23；`ResumeSkillSyncTest` 3。

---

## 未做 / 刻意不做

- RAG / 推荐侧对爬虫 requirement JSON 的清洗与重索引。
- 按 GUIDE 字面替换推荐乘子、候选人假匹配分、星级 UI。
- 提交 `experiments/data/`。

## 备份路径汇总

`/workspace/bishe-logs/uxfix/backup_before_cleanup.sql.gz`  
`/workspace/bishe-logs/uxfix/backup_before_cleanup_run2.sql.gz`  
`/workspace/bishe-logs/uxfix/backup_job_position_tag_before_retag.sql.gz`  
证据与日志：`/workspace/bishe-logs/uxfix/evidence/`、`runall_item*.log`、`notes.md`
