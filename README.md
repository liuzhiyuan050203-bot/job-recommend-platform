# 基于 Spark 与 RAG 的高校就业推荐平台

毕业设计《基于 Spark 与 RAG 的高校就业推荐平台的设计与实现》的工程代码，仓库根目录 `/workspace/bishe`。平台面向学生、企业和学校管理员，提供账号与资料、内容社区、招聘投递，以及后续的离线分析、推荐和智能问答。

## 项目简介

三类角色：

1. **学生**：维护档案与技能、浏览公告和面经、检索并收藏职位、投递简历、跟踪面试。
2. **企业**：维护企业资料并提交资质、发布与上下架职位、筛选候选人、安排笔试和面试。
3. **管理员**：审核账号、企业资质、职位和社区内容，维护轮播图、资讯、职位分类和技能标签。

功能模块：

| 模块 | 状态 | 内容 |
| :--- | :--- | :--- |
| 认证与权限 | 已实现 | 注册登录、JWT、角色拦截、账号启用/禁用后旧令牌立即失效 |
| 模块一 基础业务 | 已实现 | 学生档案与技能、企业资料与资质审核、轮播图与资讯、面经评论、分类与技能标签 |
| 模块二 招聘流程 | 已实现 | 职位发布与审核上架、多条件检索、收藏、简历、投递状态机、面试通知 |
| Spark 分析 | 已实现 | 离线清洗、薪资统计、技术趋势、地区分布与薪资回归 |
| 推荐 | 已实现 | 用户余弦协同过滤与技能内容匹配融合，结果回写 `spark_recommend`，离线指标写入 `spark_recommend_eval` |
| RAG 智能问答 | 已实现 | 政策与面经切片、Chroma 检索、三类助手 SSE、会话与知识库管理 |
| 仪表盘与演示 | 已实现 | 公开/学生/企业/管理端 ECharts 真实数据看板、系统演示页 `/demo`、一键启停 |

## 技术栈

| 部分 | 技术 |
| :--- | :--- |
| 前端 | Vue 3、Vite、Pinia、Vue Router、Element Plus、ECharts、Axios，包管理 pnpm，端口 5173 |
| 业务后端 | Java 21、Spring Boot 3.3.5、MyBatis-Plus 3.5.7、JWT，端口 8080，上下文前缀 `/api` |
| AI 服务 | Python 3.12、FastAPI、Uvicorn，虚拟环境 `/workspace/bishe/.venv`，端口 8000 |
| 数据库 | MariaDB / MySQL，库 `job_platform`，`127.0.0.1:3306`，账号 `job` / `job123` |

统一响应为 `Result`：`code`、`msg`、`data`。分页为 `{records, total, current, size}`，单页 `size` 最大 100。

## 目录结构

```
/workspace/bishe/
├── backend/          # Spring Boot，包名 com.bishe.job
├── frontend/         # Vue 3
├── ai-service/       # FastAPI
├── db/               # schema.sql（28 张表）、seed.sql、README.md
├── scripts/          # start-mysql.sh、start-ollama.sh、start-all.sh、stop-all.sh
├── tests/
│   ├── run-all.sh    # 拉起依赖并跑完全部接口脚本
│   └── api/          # 01 认证 … 07 仪表盘图表接口
├── DEMO.md           # 答辩演示勾选清单
└── README.md
```

## 环境要求

- OpenJDK 21，`JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`
- Maven 3.9+（可使用本地 `~/.m2`）
- MariaDB 11.8+ 或 MySQL 8.0+，字符集 `utf8mb4`。应用账号不能 `CREATE DATABASE`，库需事先存在
- Node.js 与 pnpm
- Python 3.12 虚拟环境 `/workspace/bishe/.venv`

```bash
export PATH="$HOME/.local/bin:$PATH"
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
```

## 初始化数据库

```bash
bash scripts/start-mysql.sh
mariadb -h127.0.0.1 -ujob -pjob123 job_platform < db/schema.sql
mariadb -h127.0.0.1 -ujob -pjob123 job_platform < db/seed.sql
```

`schema.sql` 会重建全部表，`seed.sql` 会清空后重灌演示数据，都可以重复执行。表结构以 `db/schema.sql` 为准。

演示账号（库内为 BCrypt）：

| 用户名 | 密码 | 角色 |
| :--- | :--- | :--- |
| admin | admin123 | 管理员 |
| student | student123 | 学生（陈晓） |
| company | company123 | 企业（星澜科技，资质已通过） |

管理员重置密码后的临时口令是 `123456`。


## 5 分钟演示

答辩或验收时按下面做即可，详细勾选清单见仓库根目录 [DEMO.md](DEMO.md)，浏览器内指南见 http://localhost:5173/demo 。

```bash
export PATH="$HOME/.local/bin:$PATH"
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
bash scripts/start-all.sh          # MariaDB、Ollama、ai-service、后端 8080、前端 5173
# 浏览器打开 http://localhost:5173
# 演示结束后：bash scripts/stop-all.sh   # 默认保留 MariaDB
```

| 角色 | 用户名 | 密码 | 建议点击 |
| :--- | :--- | :--- | :--- |
| 学生 | student | student123 | 求职看板 → 职位投递 → 为你推荐 → 就业助手 |
| 企业 | company | company123 | 招聘看板 → 候选人推进状态 → 招聘助手 |
| 管理员 | admin | admin123 | 数据分析（Spark/推荐/RAG）→ 审核 → 知识库 / 数据助手 |

登录页可一键填入演示账号，也支持 `/login?demo=student`。公开首页图表与 `/student/dashboard`、`/company/dashboard`、`/admin/analytics` 均读取真实统计接口，不再使用静态占位数据。

## 启动

```bash
# MariaDB
bash scripts/start-mysql.sh

# 后端
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
cd backend
mvn -DskipTests package
java -jar target/job-backend-1.0.0.jar
# 健康检查：curl http://localhost:8080/api/health

# AI 服务（Spark 分析触发与实时薪资预测依赖它；公开统计接口只读数据库）
cd ai-service
cp -n .env.example .env
../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend
pnpm install
pnpm dev          # http://localhost:5173
pnpm build        # 产物在 frontend/dist
```

JWT 密钥读 `backend/src/main/resources/application.yml` 的 `jwt.secret`，可用环境变量 `JWT_SECRET` 覆盖（至少 32 字节）。有效期用 `JWT_EXPIRE_HOURS` 覆盖。

## 接口前缀与权限

所有接口以 `/api` 开头。

| 前缀 | 谁可以访问 |
| :--- | :--- |
| `/api/health`、`/api/public/**` | 匿名。带了有效令牌时会识别当前用户，无效令牌按匿名处理 |
| `/api/user/**` | 已登录且账号状态正常 |
| `/api/student/**` | 学生 |
| `/api/company/**` | 企业。资质未通过时只能访问 `/api/company/profile/**` |
| `/api/admin/**` | 管理员 |

未登录返回 401，角色不符返回 403。路径会先解码并去掉分号参数，因此 `/api/%61dmin/**`、`/api/admin;x=1/**` 仍按管理员接口校验。含 `%2e%2e` 或 `..` 的路径直接 400。学生和企业按编号操作帖子、评论、技能、简历、职位、投递时，只允许改自己的数据。

账号 `sys_user.status`：0 待审核，1 正常，2 禁用，3 已驳回。企业与职位、帖子、评论的 `audit_status`：0 待审核，1 通过，2 驳回。职位 `shelf_status`：0 下架，1 上架。投递 `job_application.status`：0 待初筛，1 笔试，2 面试中，3 已录用，4 未通过。

## Spark 离线分析

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
cd ai-service
../.venv/bin/python -m app.spark.run_all                       # 全部：clean → aggregate → salary_regression
../.venv/bin/python -m app.spark.run_all --tasks aggregate     # 只跑部分任务
```

- 运行模式 `local[*]`，通过 `spark.jars` 加载 MySQL JDBC 驱动（环境变量 `SPARK_JDBC_JAR`，默认 `~/.m2/repository/com/mysql/mysql-connector-j/8.3.0/mysql-connector-j-8.3.0.jar`）。
- clean：解析 `data/raw/jobs_raw.csv` 中的薪资文本、去重、城市/学历/经验规范化、剔除异常值；统计写入 `spark_task_log`。
- aggregate：从库中已审核职位聚合出 `spark_salary_stat`（省/城市/方向的均值、中位数、P25/P75）、`spark_tech_trend`（月份×技能需求与环比）、`spark_region_dist`（省份职位/企业/投递数与 6 位 adcode）。
- salary_regression：MLlib 随机森林回归预测平均月薪，模型保存在 `ai-service/data/models/salary_model`，城市×方向×学历×经验网格预测写入 `spark_salary_predict`。
- 每次运行一个 `batch_no`，新批次 `is_latest=1`，旧批次置 0，每表只保留最近 5 批。同一时间只允许一次运行。

实测（2026-10-31，8 核）：整次运行约 20 秒；CSV 3360 行 → 有效 2409（重复 200、面议 476、异常 275）；薪资统计 239 行、技术趋势 683 行、地区 16 省；模型测试集 RMSE≈1841、MAE≈1031、R2≈0.966。

演示数据中工作经验对薪资的影响较明显（经验系数：应届 1.00、一年以内 1.10、1–3 年 1.40、3–5 年 1.80、5 年以上 2.30）。预测时 2 年及以上经验按社招职位类型计算，否则按校招。例：北京·后端开发·本科，0 年约 1.97 万，3 年约 2.99 万，5 年约 3.74 万。

| 接口 | 说明 |
| :--- | :--- |
| `POST /api/admin/spark/run` | 管理员触发分析（body 可选 `{"tasks":[...]}`），运行中再次触发返回 409「已有任务运行中」 |
| `GET /api/admin/spark/tasks` | 任务日志分页，可按 `batchNo`/`status` 过滤 |
| `GET /api/public/stats/overview` | 职位/企业/学生/投递数、平均月薪、城市数、最近成功批次 |
| `GET /api/public/stats/salary` | 薪资统计明细与按方向、按城市汇总，可按 `city`/`tech_direction` 过滤 |
| `GET /api/public/stats/tech-trend?top=10&months=12` | ECharts 结构：`months` + `series` + 热门技能排行 |
| `GET /api/public/stats/region` | 省份地图数据 `[{name,value,adcode,companyCount,avgSalary,applyCount}]` |
| `GET /api/public/stats/salary/predict` | 转发 FastAPI 实时预测（`city`、`techDirection`、`education` 1–4、`experienceYears`、`skills`），分析服务不可用时返回 503 |
| `GET /api/public/stats/hiring-demand?months=12` | 近 N 个月职位发布量与投递量（图表） |
| `GET /api/student/dashboard` | 学生投递漏斗、技能雷达、档案摘要、推荐 Top |
| `GET /api/company/dashboard` | 企业职位表现、投递状态、候选人技能词频 |
| `GET /api/admin/dashboard/overview` | 平台概览 + 最近 Spark 批次 + 推荐 NDCG + AI 会话/消息数 |

FastAPI 侧：`POST /spark/run`、`GET /spark/tasks`、`GET /spark/tasks/{batch_no}`、`GET /spark/salary/predict`。管理端页面 `/admin/analytics` 展示图表、触发按钮和任务列表。

## 混合推荐

默认的 `run_all` 仍只跑清洗、聚合和薪资回归。推荐单独触发，避免拖慢分析：

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
cd ai-service
../.venv/bin/python -m app.spark.run_all --tasks recommend
```

也可以由管理员在 `/admin/recommend` 点击运行，或调用 `POST /api/admin/recommend/run`（FastAPI `POST /recommend/run`）。运行中再次触发返回 409。

算法（离线任务 `recommend`，写入 `spark_task_log`）：

- **协同过滤**：浏览 1、收藏 3、投递 5，按全体行为最大时间做 45 天半衰期衰减，同一学生对同一职位汇总后 `log1p`。在留出集上比较用户-用户余弦（共同交互收缩、保留正相关邻居）和 MLlib 隐式 ALS（rank 8、6 轮），按 NDCG@10 择优。学生规模约 200，余弦矩阵放在 Driver 上，并保存为 `ai-service/data/recommend/cf_model.pkl` 供实时推荐复用。
- **内容匹配**：技能熟练度与职位标签的余弦、期望方向、期望城市、学历是否达到要求、专业是否出现在职位名称或任职要求中。学历不够的职位再乘 0.35。
- **融合**：线性 `alpha×CF+(1-alpha)×内容`，或门控（内容分高的职位才放大协同信号）。`alpha`、是否按活跃度缩放、线性或门控都在留出集上按 NDCG@10 选择。没有行为、或行为只落在无人共同交互的职位上（协同过滤整行为 0）的学生，按冷启动用 0.75×内容 + 0.25×近期行为热度。
- **过滤**：只推荐已上架、已审核、未删除且企业资质通过的职位，并排除该学生已投递的职位。每名有档案的学生写 Top20，算法 1/2/3 各一份（1 协同过滤，2 内容，3 融合），含匹配分、两项分子分、名次和中文理由。新批次 `is_latest=1`，只保留最近 5 批。
- **评估**：按学生把收藏/投递按时间留出约 20%（测试对上的浏览一并从训练集去掉），在未见过的在架职位上计算 Precision/Recall/NDCG@5、10、20 和目录覆盖率，并与热门基线对比。结果在 `spark_recommend_eval` 和 `ai-service/data/recommend/eval_metrics.json`。

学生端 `GET /api/student/recommend` 读最新融合结果；该学生还没有批次时调用 `GET /recommend/user/{id}` 实时计算；分析服务不可用时用技能、方向、城市和投递热度做 SQL 兜底。职位详情的相似职位走 `GET /api/public/jobs/{id}/similar`，按标签重合、同方向、同城市排序。页面：学生「为你推荐」、首页推荐条、职位详情「相似职位」、管理端「推荐评估」。

本次演示数据上，用户余弦的留出 NDCG@10（0.582）高于隐式 ALS（0.287），融合（线性、alpha=0.45、不按活跃度缩放）高于协同过滤、内容匹配和热门基线。整次任务约 12 秒（含 Spark 启动）。具体指标以 `spark_recommend_eval` 中 `is_latest=1` 的行为准：

| 算法 | P@10 | R@10 | NDCG@10 | 覆盖率@10 |
| :--- | ---: | ---: | ---: | ---: |
| 协同过滤（用户余弦） | 0.1385 | 0.6125 | 0.5820 | 0.1907 |
| 内容匹配 | 0.0935 | 0.4150 | 0.3553 | 0.3160 |
| 融合 | 0.1510 | 0.6725 | 0.6190 | 0.3004 |
| 热门基线 | 0.0050 | 0.0225 | 0.0162 | 0.0075 |

留出集每名学生只有少量收藏/投递，因此 Recall 偏高、Precision 偏低；演示行为按方向和城市聚集，指标比真实场景乐观。

`tests/api/05-recommend.sh` 覆盖：未登录 401、企业/管理员访问学生推荐 403、学生访问推荐评估 403、附带 `userId` 参数仍只返回自己的推荐、推荐职位均在架且已审核、不含已投递职位、企业下架后立即从推荐和相似职位中消失、新注册学生（无行为）冷启动有推荐且有理由、投递后从推荐中移除、相似职位不含自身、评估中融合 NDCG@10 高于热门与内容匹配。

## Phase 5 智能问答

页面：学生「就业助手」`/student/assistant`，企业「招聘助手」`/company/assistant`，管理员「数据助手」`/admin/assistant`，知识库管理 `/admin/knowledge`。

调用链：

```
Vue fetch（Authorization: Bearer JWT）
  → Spring Boot SSE 代理（校验角色，/api/{role}/ai/chat/stream）
    → ai-service（请求头 X-Internal-Token、X-User-Id、X-User-Role）
      → RAG（Chroma 集合 job_knowledge，嵌入 BAAI/bge-small-zh-v1.5）或角色工具
        → LLM（Ollama 或任意 OpenAI 兼容接口）
```

前端不直连 8000。后端在转发前补一条 `data: {"type":"session","session_id":...,"title":"..."}`，随后原样转发 `meta`、`status`、`tool`、`sources`、`delta`、`error`、`done`，最后是 `data: [DONE]`。`meta.mode` 为 `online` 或 `offline`。

### 启动与停止

```bash
bash scripts/start-all.sh              # MariaDB、本机 Ollama、ai-service、后端、前端
bash scripts/start-all.sh --no-frontend
bash scripts/stop-all.sh               # 停掉本次拉起的进程，默认保留 MariaDB
bash scripts/stop-all.sh --with-mysql
```

已经健康的端口不会重复启动。日志在 `logs/`（已 gitignore），PID 在 `.run/`。脚本会读取 `ai-service/.env` 里尚未导出的变量；调用前导出的 `AI_INTERNAL_TOKEN`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TOOL_CALLING` 会原样传给 ai-service 和后端。`rag_document` 为空时会执行 `python -m app.rag.ingest --all`。

也可以按下面的方式分开启动。

### Ollama 与 qwen2.5:3b

```bash
bash scripts/start-ollama.sh
```

脚本若发现 `11434` 上没有服务，会 `nohup ollama serve`（日志 `/tmp/ollama-serve.log`）。模型默认 `qwen2.5:3b`：先 `ollama pull`，失败再从 Hugging Face 下载 `qwen2.5-3b-instruct-q4_k_m.gguf` 并用 Modelfile `ollama create`。可用 `OLLAMA_MODEL`、`HF_ENDPOINT` 覆盖。ai-service 默认 `LLM_BASE_URL=http://127.0.0.1:11434/v1`、`LLM_MODEL=qwen2.5:3b`、`LLM_API_KEY=ollama`。这台机器是 CPU，一条回答大约 2–40 秒。

`LLM_BASE_URL` 不是本机地址时，`start-all.sh` 不会启动 Ollama。

### 换成 DeepSeek 等在线模型

在 `ai-service/.env` 或启动环境里设置（不要把真实密钥写进仓库）：

```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-chat
LLM_TOOL_CALLING=auto
```

`LLM_TOOL_CALLING`：

| 值 | 行为 |
| :--- | :--- |
| `true` / `1` / `yes` / `on` | 先让模型用 LangChain 选工具，没有合法调用再走关键词路由 |
| `false` / `0` / `no` / `off` | 只用关键词和槽位路由 |
| `auto`（默认） | 基址在本机，或模型名里的参数量不超过 8B 时，只用关键词路由；否则同 `true` |

后端和 ai-service 都要能读到同一个 `AI_INTERNAL_TOKEN`。改完后重启两边。

### 离线模式

`LLM_PROVIDER=offline`，或探测 `LLM_BASE_URL/models` 失败（连不上、超时、非 2xx）时，`meta.mode` 为 `offline`。回答以「【离线模式】」开头，附上工具结果表格和知识库摘录（`OfflineGenerator` 按字二元组抽句），HTTP 仍是 200 的 SSE，而不是 500。显式检索和统计不依赖大模型。

### 重建知识库

```bash
cd ai-service
../.venv/bin/python -m app.rag.ingest --all
```

`--all` 清空 Chroma 与 `rag_document` 后，写入 `data/knowledge/*.md`、公告、在架职位和管理员上传。只更新一类来源用 `--source knowledge|cms|jobs|uploads`。管理端也可 `POST /api/admin/ai/knowledge/reindex`。

### 内部令牌

`AI_INTERNAL_TOKEN` 必须与后端 `fastapi.internal-token`（`application.yml` 的 `${AI_INTERNAL_TOKEN:change-me-internal-token}`）完全一致。比较使用常量时间。日志和接口响应里不会出现令牌。生产环境一定要改掉示例值，并只放在两边的环境变量或本机 `.env` 中。

### 角色助手示例问题

| 角色 | 示例 |
| :--- | :--- |
| 学生 | 三方协议怎么签？ / 推荐适合我的岗位 / 北京后端应届薪资大概多少 / 我投 Java 后端还缺什么技能 |
| 企业 | 帮我写一个 Java 后端校招 JD / 帮我筛选我发布职位的候选人 / 列出我发布的职位 |
| 管理员 | 哪个城市岗位最多 / 本月热门技能有哪些 / 平台概况 / 推荐算法评估指标 |

「有哪些 / 排行 / top / 前几」类技能问题会列出技术趋势前 5 名（名称、需求量、环比）。「增长最快」仍只给第一名。推荐和检索职位按工具结果逐条写出城市和薪资。引用写成 `[资料2]` 或 `【资料2】` 时会收成 `[2]`，编号超过资料条数的标记会被丢掉。

### 接口

对话走 SSE：前端 `fetch` 带 `Authorization: Bearer`，后端按行转发 ai-service 的事件。

已有库增加助手消息的 `extra` 列（JSON 文本，含 `sources`、`tools`、`latency_ms`、`first_token_ms`）：

```bash
mariadb -h127.0.0.1 -ujob -pjob123 job_platform < db/migrations/phase5_ai_session.sql
```

| 接口 | 说明 |
| :--- | :--- |
| `POST /api/{student\|company\|admin}/ai/chat/stream` | 体 `{question, sessionId?}`。`question` 1–2000 字。无 `sessionId` 时创建会话，标题取问题前 20 字。会话必须属于当前用户且角色一致，否则 404。响应 `text/event-stream`，超时约 300 秒 |
| `GET /api/{role}/ai/sessions` | 当前用户、当前角色的会话，按更新时间倒序，默认 50 条 |
| `GET /api/{role}/ai/sessions/{id}/messages` | 该会话消息；不是自己的返回 404 |
| `DELETE /api/{role}/ai/sessions/{id}` | 逻辑删除自己的会话 |
| `PUT /api/{role}/ai/sessions/{id}` | 重命名，体 `{"title":"..."}` |
| `GET /api/admin/ai/knowledge/documents` | 文档分页，可按 `docType`、`sourceType`、`q` 过滤 |
| `GET /api/admin/ai/knowledge/stats` | 文档数、切片数、向量条数 |
| `POST /api/admin/ai/knowledge/upload` | multipart：`file`（.md/.txt，≤512KB）、`title`、`docType` |
| `POST /api/admin/ai/knowledge/reindex` | `docKey` 或 `source=knowledge\|cms\|jobs\|uploads\|all`。职位重建大约几十秒 |
| `DELETE /api/admin/ai/knowledge/documents?docKey=` | 删除一个逻辑文档 |
| `GET /api/admin/ai/knowledge/search?q=` | 调试检索 |

未登录 401，角色不符 403。AI 服务不可达时，流式接口仍保存用户消息，并返回 `{"type":"error","msg":"AI 服务暂不可用"}`；知识库接口返回明确错误，不回传堆栈。用户编号只从 JWT 读取，内部令牌不出现在日志和响应里。

ai-service 侧：没有资料切片时提示词禁止 `[1]`、`[2]`，流式输出会把 `[资料n]`、`【资料n】` 收成 `[n]`，并丢掉编号大于资料条数的标记，`done.answer` 与已经推送的文字一致。管理员问城市岗位数量走 `city_distribution`（在架职位按城市计数），问省份仍走 `region_distribution`。对不上统计意图时，用平台概况加知识库资料回答。

## 运行测试

```bash
bash tests/run-all.sh
```

脚本在 MariaDB 未运行时调用 `scripts/start-mysql.sh`；8080 没有健康检查时会打包并后台启动后端（日志 `/tmp/job-backend-test.log`），结束时关掉自己启动的进程。`tests/api/06-rag.sh` 在 ai-service 的 `/health` 不可达时打印 SKIP、记 0 失败并以 0 退出，其余脚本照常汇总。ai-service 在、但大模型不可达时，06 仍应通过（离线模式）。流式断言的 `curl --max-time` 为 180 秒。任一断言失败则退出码非 0。

当前结果（`bash tests/run-all.sh`，2026-10-31，ai-service 已启动；未启动时 04/05 中依赖 FastAPI 的断言记为 SKIP，05 的冷启动走数据库兜底，06 整段 SKIP）：

| 脚本 | PASS | FAIL |
| :--- | ---: | ---: |
| 01-auth.sh | 35 | 0 |
| 02-module1.sh | 165 | 0 |
| 03-recruitment.sh | 89 | 0 |
| 04-spark.sh | 55 | 0 |
| 05-recommend.sh | 56 | 0 |
| 06-rag.sh | 92 | 0 |
| 07-dashboard.sh | 49 | 0 |
| 合计 | 541 | 0 |

同一轮还通过了 `cd backend && mvn -q -DskipTests package` 和 `cd frontend && pnpm build`。ai-service 停掉后再跑一遍：06 打印 SKIP，记 PASS=0 FAIL=0；01–03 仍是 35 / 165 / 89；04 为 49（跳过分析触发、实时预测和 FastAPI 任务列表）；05 为 54（冷启动走数据库兜底，跳过推荐任务触发与 FastAPI 相似职位）。合计约 441（含 07 仪表盘；06 整段 SKIP），失败 0。
