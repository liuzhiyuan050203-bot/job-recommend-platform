# 演示数据生成器

`generate_demo_data.py` 用固定随机种子生成校园招聘演示数据，写入 MySQL 的 `job_platform`，并另存一份带噪声的爬虫原始 CSV。不实现推荐或 RAG。统计时间锚点固定为 **2026-10-31**，同一 `--seed` 重复运行得到同一批数据。

## 运行

数据库需已执行 `db/schema.sql` 和 `db/seed.sql`。MySQL 未启动时先执行 `bash scripts/start-mysql.sh`。

```bash
export PATH="$HOME/.local/bin:$PATH"
/workspace/bishe/.venv/bin/pip install -r data/requirements.txt
/workspace/bishe/.venv/bin/python data/generate_demo_data.py
/workspace/bishe/.venv/bin/python data/generate_demo_data.py --seed 20261031
/workspace/bishe/.venv/bin/python data/generate_demo_data.py --clean
```

`--seed` 默认 `20261031`。`--clean` 只删除本生成器写入的演示数据，并删除 `data/raw/jobs_raw.csv`。

连接参数可用环境变量覆盖：

| 变量 | 默认 |
| --- | --- |
| `MYSQL_HOST` | `127.0.0.1` |
| `MYSQL_PORT` | `3306` |
| `MYSQL_USER` | `job` |
| `MYSQL_PASSWORD` | `job123` |
| `MYSQL_DATABASE` | `job_platform` |

企业账号 `demo_corp_01`–`demo_corp_30`、学生账号 `demo_stu_001`–`demo_stu_200` 的密码都是 `Demo@123`（库内为固定盐的 BCrypt，兼容 Spring Security `BCryptPasswordEncoder`）。

## 幂等与清理范围

识别规则：

- 用户名匹配 `^demo_(corp|stu)_[0-9]+$`
- 企业统一社会信用代码匹配 `^DEMO[0-9]{14}$`
- 职位、收藏、投递、行为日志通过上述企业或学生归属删除

再次运行时先按外键依赖删除这些行，再插入。`admin` / `student` / `company`、测试脚本注册的账号、以及它们的职位和投递都不会删除。职位分类和技能标签按**名称不存在才插入**，清理时也不删除，因此重复运行不会重复补齐。

地址和福利字段里不写演示标记。

## 默认种子下的规模

以下为 `--seed 20261031` 的写入量（分类和技能标签的“本次写入”取决于库里是否已有同名行；下面按名称集合说明）：

| 数据 | 规模 |
| --- | --- |
| 企业 `ent_company` | 30，资质已通过，行业、规模、城市不同 |
| 学生 | 200 份档案、200 份默认简历、约 942 条技能（每人 3–8 项） |
| 职位 | 3200，其中约 129 条下架，其余 `audit_status=1` 且 `shelf_status=1` |
| 职位技能 | 约 12913 条，每个职位 3–6 个标签，以本方向为主 |
| 行为日志 | 24233 条（浏览 21351、收藏 2163、投递 719），权重 1/3/5，时间在 2026-05 至 2026-10 |
| 收藏 / 投递 | 与收藏、投递行为一一对应；投递状态为待初筛，并有一条状态日志 |
| 发布月份 | 2025-11 至 2026-10，共 3200 条。整体随时间温和增长，3 月春招约 349 条、9 月约 417 条、10 月约 447 条，2025-12 约 159 条为低点 |

学生行为以「期望方向 + 期望城市」为主，同组学生会集中浏览同一批职位，并带少量跨方向探索，便于后续 User-CF。职位上的浏览、收藏、投递次数与上述行为条数一致。

补齐的叶子分类（父类「技术研发」或新建的「产品设计」）包括：云原生开发、算法工程、测试开发、运维开发、移动开发、嵌入式开发、产品经理、UI设计。`job_position.tech_direction` 与 `skill_tag.direction` 使用叶子分类名。技能标签共 57 个（含种子里已有的 Java、Spring Boot、Spark 等，以及「大模型」）。名称已存在则不覆盖原方向。「大模型」不参与基础随机抽样，避免打乱原有标签序列；后期月份会把部分人工智能、算法工程岗位上的标签替换成「大模型」或 PyTorch，因此这两个标签的月度占比逐月上升。各方向职位总数、月薪、城市、学历、经验、职位标签条数和行为条数保持不变，行为时间会随新的发布时间落到职位发布之后。

人工智能与算法工程占当月职位的比例由 2025 年末约 10% 升到 2026 年 8–10 月约 23%，测试开发由约 13% 降到约 5%。

默认种子下各方向月薪中点均值（含各城市、学历和经验，单位元）大约为：算法工程 22565、人工智能 19849、数据开发 18471、云原生开发 17267、后端开发 16723、移动开发 16104、前端开发 15411、嵌入式开发 15278、产品经理 14667、运维开发 12420、测试开发 11555、UI设计 11109。经验系数为：经验不限/应届 1.00、一年以内 1.10、一到三年 1.40、三到五年 1.80、五年以上 2.30，社招岗位的经验对薪资影响明显。一线城市、应届、本科、校招的后端岗位中点均值约 2.0 万；二线同口径大约低 20%–35%。

20 个城市均有职位，一线多于二线。省份使用地图口径（如广东、北京）。

## 原始 CSV

`data/raw/jobs_raw.csv` 为 UTF-8、带表头，**不入库**。默认种子下 3360 行，其中 3200 行与职位对应，另有 160 行（约 5%）是完全重复行。

字段：`title, company, city, salary_text, education_text, experience_text, tags, publish_date, direction`。

城市、薪资、学历、经验和日期故意不统一，例如 `上海市`、`深圳 南山区`、`15-25K·14薪`、`8000-12000元/月`、`面议`、`200-300元/天`、`30-50万/年`，以及少量空字段和非法值，供后续 Spark 清洗演示。

## 测试夹具清理与投递漏斗再平衡

UX 审计（`experiments/ux_audit/REPORT.md` P1-1/P1-6/P1-10）发现演示账号被接口测试数据淹没：演示企业下几十个「招聘流程测试*」「越权隔离职位*」职位，演示学生几十条「已录用」测试投递和测试默认简历，而生成器写入的投递又全部停在「待初筛」，看板呈倒漏斗。处理分两步，执行前先备份：

```bash
/opt/mysql/bin/mysqldump --no-defaults --protocol=tcp -h127.0.0.1 -ujob -pjob123 --single-transaction \
  --no-tablespaces --routines --triggers --default-character-set=utf8mb4 job_platform | gzip > backup.sql.gz
.venv/bin/python data/cleanup_test_fixtures.py            # 预览
.venv/bin/python data/cleanup_test_fixtures.py --apply    # 逻辑删除历史夹具
.venv/bin/python data/rebalance_demo_funnel.py            # 预览（事务回滚）
.venv/bin/python data/rebalance_demo_funnel.py --apply    # 写库
```

- `cleanup_test_fixtures.py`：按账号归属和标题前缀识别测试夹具（非 `admin/student/company/demo_*/real_*` 的学生企业账号；演示企业下「招聘流程测试*」「越权隔离职位*」「UX-IDOR*」等职位；演示学生名下测试简历；「Rust测试」标签和「测试分类」），连带投递、日志、面试、收藏、行为日志一起 `deleted=1`，重算受影响职位的投递 / 收藏数，并把演示学生默认简历恢复为「陈晓-校招简历」。不改任何正常投递的状态。
- `rebalance_demo_funnel.py`：给演示企业在架职位补 2×12 份投递（选技能重合高的 `demo_stu_*`）、给演示学生补 5 份同方向投递（备注「校园招聘网申（演示补充）」，只补一次）；再把只有「提交投递」一条日志的待初筛投递按投递时长和技能匹配度推进：HR 处理概率随投递天数上升（上限 75%），初筛 / 笔试 / 面试通过率随技能匹配度上升，每一步按状态机写日志、笔试和面试写 `job_interview`，所有时间不晚于锚点 `--anchor`（默认 2026-11-03 00:00），仍在进行中的笔试 / 面试排在锚点之后几天。每条投递用 `random.Random(f"{seed}:{id}")` 抽样，同一库状态、同一种子结果一致；重复执行不会再次推进。预览模式回滚后自增编号会前移，所以预览与正式执行的个别结果可能不同。
- 接口测试自身不再遗留数据：`tests/api/lib.sh` 的 `purge_fixtures` 在每个脚本退出时删除本次注册的账号、发布的职位和简历，并恢复演示学生原默认简历；`tests/api/11-demo-data.sh` 在最后检查这些约束。

2026-11-03 执行结果：清理 325 个临时账号、46 个测试职位、82 份测试简历、89 条测试投递；补充投递 29 条；全平台投递 待初筛 339 / 笔试 9 / 面试中 66 / 已录用 65 / 未通过 336。之后重新跑了 Spark 清洗聚合与推荐批次。

## 真实职位技能标签修正（retag_real_jobs.py）

早期导入真实职位时，标题里匹配不到技能的岗位会被塞上默认的 Java / Spring Boot / MySQL，
导致「游戏体验设计」「产品运营」这类岗位在推荐理由里出现后端技能。`retag_real_jobs.py`
只处理 `real_*` 企业下、标签里没有任何本方向技能的职位：按标题关键词重新打标签，研发方向
或标题明确是产品/设计岗位时才补本方向默认技能（产品经理：需求分析/原型设计/Axure；
UI设计：交互设计/Figma/Sketch），销售、人事、运营类岗位宁可不打标签也不编造技能。

```bash
.venv/bin/python data/retag_real_jobs.py          # 只预览
.venv/bin/python data/retag_real_jobs.py --apply  # 写库，幂等，重复执行无变化
```

`import_real_jobs.py` 新导入时复用同一套规则。改标签后需在管理端重跑一次推荐批次。
