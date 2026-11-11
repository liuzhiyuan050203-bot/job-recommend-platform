# 真实校招数据说明（毕业论文用）

## 概述

本平台除可复现的 `demo_` 前缀演示数据外，另通过公开校园招聘接口同步了一批**真实校招职位**，用于展示与大厂校招官网一致的职位标题、城市与投递链接。同步工具为开源 CLI [`@ha7ch/job-pro`](https://github.com/HA7CH/job-pro)（封装各公司官方/校园 ATS 公开检索接口），**不登录、不抓取 BOSS 直聘 / 智联等第三方聚合站**。

| 项目 | 内容 |
|------|------|
| 抓取时间 | 2026-11-01 02:28:54 ~ 02:31:55 Asia/Shanghai |
| 工具 | `npx @ha7ch/job-pro@latest`，封装于 `data/job_pro_client.py` / `data/crawl_campus_jobs.py` |
| 范围 | `--scope campus`，空关键词分页拉取 |
| 限速 | 调用间隔 ≥1.1s |
| 入库脚本 | `data/import_real_jobs.py`（幂等，账号前缀 `real_`，信用代码前缀 `REAL`） |
| 原始落盘 | `data/raw/campus_20261101/*.jsonl`、`summary.json` |

## 真实 vs 合成

| 维度 | 真实（本批） | 合成（demo_） |
|------|-------------|---------------|
| 职位标题 / 城市 / 投递链接 | 来自企业校园招聘公开 API | `data/generate_demo_data.py` 按种子生成 |
| 薪资区间 | **估算**（按技术方向×城市档位，与演示生成器同口径），官网多数不返回公开月薪 | 按方向/城市/学历公式生成 |
| 岗位描述正文 | 同步元数据 + 官网投递链接；完整 JD 以官网为准 | 模板生成 |
| 企业账号 | `real_<company_key>` / `Real@123` | `demo_corp_*` / `Demo@123` |
| 行为日志 | 可选：由现有学生对真实职位注入浏览/收藏/投递，供协同过滤有信号 | 大规模结构化偏好日志 |
| 种子账号 | 不改动 `admin` / `student` / `company` | 同左 |

## 来源与数量（本批）

合计 **1758** 条，覆盖 **16** 家企业（计划 18 家；美团接口网络失败跳过；华为校园通道返回 total=0）。

| 公司 | company_key | 来源域名 | 条数 |
|------|-------------|----------|------|
| 字节跳动 | bytedance | jobs.bytedance.com | 280 |
| 腾讯 | tencent | join.qq.com | 180 |
| 阿里巴巴 | alibaba | campus-talent.alibaba.com | 180 |
| 小米 | xiaomi | xiaomi.jobs.f.mioffice.cn | 180 |
| 网易 | netease | hr.163.com | 150 |
| 小红书 | xiaohongshu | job.xiaohongshu.com | 150 |
| 快手 | kuaishou | campus.kuaishou.cn | 150 |
| 京东 | jd | campus.jd.com | 120 |
| 哔哩哔哩 | bilibili | jobs.bilibili.com | 100 |
| OPPO | oppo | careers.oppo.com | 80 |
| 米哈游 | mihoyo | jobs.mihoyo.com / ats | 60 |
| 蚂蚁集团 | antgroup | hrcareersweb.antgroup.com | 49 |
| 拼多多 | pdd | careers.pinduoduo.com | 34 |
| 百度 | baidu | talent.baidu.com | 20 |
| 滴滴出行 | didi | talent.didiglobal.com | 15 |
| 携程 | trip | careers.ctrip.com | 10 |

跳过记录：

- **美团** `meituan`：`network error: fetch failed`
- **华为** `huawei`：接口成功但 campus total=0

部分公司单页返回少于 `page-size`（如滴滴、百度、蚂蚁），脚本按实际返回条数入库，不强制补齐。

## 样例（标题 + 官网投递链接）

- 字节跳动 | 后端开发工程师（AI效能工具） - 开发者服务 | https://jobs.bytedance.com/campus/position/7667822947755854133/detail
- 腾讯 | Agent开发工程师 | https://join.qq.com/post_detail.html?postid=1282707395466077184
- 阿里巴巴 | 面向 AI Coding 的下一代高性能推理引擎与智能成本治理体系-阿里星 | https://campus-talent.alibaba.com/campus/position/199907640008
- 小红书 | 【REDstar】电商算法工程师 | https://job.xiaohongshu.com/campus/position/20886
- 快手 | 技术与资源解决方案工程师 | https://campus.kuaishou.cn/recruit/campus/e/#/campus/job-info/?code=be34668af00446e8b6f986020becd65a
- 百度 | 北京-AI测试开发工程师(J101055) | https://talent.baidu.com/jobs/detail/GRADUATE/6061be03-f92b-4430-a1b8-9168de0f91f6
- OPPO | AI系统工程师（AI工程化方向） | https://careers.oppo.com/#/campus/talent/positionDetail/1843
- 网易 | 强化学习算法实习生（游戏AI方向）---广州 | https://hr.163.com/job-detail.html?id=79458
- 米哈游 | UI蓝图实习生 | https://jobs.mihoyo.com/#/position/9216

完整清单见 `data/raw/campus_20261101/all_jobs.jsonl`。

## 入库字段与溯源

每条 `job_position`：

- `audit_status=1`、`shelf_status=1`，`job_type` 默认校招(3)，标题含「实习」则为实习(2)
- `tech_direction` / `category_id`：标题关键词映射到叶子分类（人工智能、算法工程、后端开发等）
- `job_position_tag`：标题关键词匹配已有 `skill_tag`
- `description` 首行含官网投递链接；`requirement` 存 JSON provenance（`company_key`、`source`、`post_id`、`apply_url`、`crawled_at`）
- `welfare` 存投递链接摘要

企业：`sys_user.username=real_<key>`，`ent_company.credit_code=REAL...`，资质已通过。

## 复现命令

```bash
export PATH="$HOME/.local/bin:$PATH"
/workspace/bishe/.venv/bin/python data/crawl_campus_jobs.py --max-total 2200
/workspace/bishe/.venv/bin/python data/import_real_jobs.py \
  --input data/raw/campus_YYYYMMDD \
  --inject-behaviors --append-csv
# 如需清掉 demo 职位再只留真实数据（慎用）：
#   ... --replace-demo-jobs --replace-csv
```

导入后触发 Spark 清洗/聚合/薪资回归与混合推荐（需 ai-service）：

```bash
curl -s -X POST http://127.0.0.1:8000/spark/run \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: $AI_INTERNAL_TOKEN" \
  -d '{"tasks":["clean","aggregate","salary_regression"]}'
curl -s -X POST http://127.0.0.1:8000/recommend/run \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: $AI_INTERNAL_TOKEN" \
  -d '{}'
```

## 伦理与声明

- 仅使用企业官方校园招聘站点的**公开检索接口**，遵守工具默认限速。
- 数据用于毕业设计演示与统计分析，投递请跳转官网完成；平台不代投、不发送邮件。
- 薪资字段为估算值，论文与演示中均需注明「非官网公示薪资」。

---

## 公开真实薪资数据集（薪资回归用，与上方「校招职位」无关）

校招入库职位的 `salary_min/max` 是按方向×城市档位**估算**的，**不能当作薪资回归的真值**（见上文「真实 vs 合成」）。论文第×章薪资预测实验改用下列两个 MIT 许可的公开招聘数据集，清洗脚本与复现命令见 `experiments/salary/prepare_real_salary.py`。

| 数据集 | 仓库 / 提交 | 抓取时间（文件元数据） | 原始 → 清洗后 | 许可 | 说明 |
|--------|-------------|------------------------|---------------|------|------|
| BOSS 直聘 IT 职位 | [poboll/bosszhipin_spider](https://github.com/poboll/bosszhipin_spider) `@3d70ae3` | Excel 创建时间 **2023-05-08**（北京时间） | 15897 → 去重 9459 → **9269** | MIT（`data/real_salary/LICENSE.bosszhipin_spider.txt`） | 含职位名、城市、学历、经验、公司规模、技能标签、月薪；方向以 Java/后端/测试为主，覆盖约 18 城 |
| 前程无忧 51job | [wangjksjtu/Data-Mining-51Job](https://github.com/wangjksjtu/Data-Mining-51Job) `@31e9a01` | 仓库提交 **2018-06-25**（UTC+8 次日凌晨） | 71641 → **40896**（仅 IT 职类） | MIT（`data/real_salary/LICENSE.Data-Mining-51Job.txt`） | 年薪已 ÷12 转月薪；有城市/学历/经验/公司规模/行业，**无自由文本职位名**（仅职类标签），薪资水平偏旧 |

清洗口径（与平台特征对齐）：

- 学历映射到 `{专科,本科,硕士,博士,不限}`；超出该刻度的行丢弃。
- 城市映射到平台 `CITY_PROVINCE`；无法映射的丢弃。
- 方向用关键词规则归入平台 12 个叶子方向，否则「其他」。
- 月薪保留区间 `[1000, 100000]`；BOSS 日薪/时薪等非月薪丢弃。
- 输出列见 `data/real_salary/{boss_2023,job51_2018}.csv`；`manifest.json` 含 sha256 与丢弃统计。

**时间差与池化模型**：51job 为 2018、BOSS 为 2023，绝对薪资水平不可直接混训。实验中的生产候选模型 `pooled_real` 在特征中加入 `data_year`（2018/2023），预测时固定为 2023，相当于用年份协变量吸收水平漂移；报告中仍分别给出两数据集上的指标。校园估算薪资集 `campus_estimated` 仅作「虚高 R²」对照，**不参与生产模型选型**。

复现：

```bash
.venv/bin/python experiments/salary/prepare_real_salary.py
.venv/bin/python experiments/salary/run_salary_experiment.py --folds 5
```

---

## 外部扩充库：飞书招聘公开门户（2026-11-11）

`data/crawl_feishu_ats.py` 从 12 家企业的 `*.jobs.feishu.cn` 公开门户抓取职位，共 1757 条（不登录，请求间隔 1.2 s）。`data/import_ats_jobs.py` 只把其中 600 条 IT 岗导入为 `job_position.data_source='ext_ats'`，账号为 `ext_*`，信用代码前缀 `EXTA`。

这批职位保存了官网 JD 原文。薪资是估算值，不参与薪资训练，前台排在核心库之后。

Moka 的接口返回加密数据，已放弃该源。详见 `experiments/data_improve/REPORT.md` 第 4 节。
