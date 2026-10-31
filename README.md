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
| Spark 分析 | 已实现 | 离线清洗、薪资统计、技术趋势、地区分布与薪资回归。推荐与 RAG 仍为后续 |
| 推荐 | 后续 | User-CF 与技能内容匹配，结果回写 `spark_recommend` |
| RAG 智能问答 | 后续 | 政策与面经切片、Chroma 检索、多角色智能体 SSE |

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
├── db/               # schema.sql（27 张表）、seed.sql、README.md
├── scripts/          # start-mysql.sh
├── tests/
│   ├── run-all.sh    # 拉起依赖并跑完全部接口脚本
│   └── api/          # 01 认证、02 模块一、03 招聘
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

# AI 服务（后续模块使用，当前业务接口不依赖它）
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

## 运行测试

```bash
bash tests/run-all.sh
```

脚本在 MariaDB 未运行时调用 `scripts/start-mysql.sh`；8080 没有健康检查时会打包并后台启动后端（日志 `/tmp/job-backend-test.log`），结束时关掉自己启动的进程。任一断言失败则退出码非 0。

当前结果（`bash tests/run-all.sh`，2026-10-30）：

| 脚本 | PASS | FAIL |
| :--- | ---: | ---: |
| 01-auth.sh | 35 | 0 |
| 02-module1.sh | 165 | 0 |
| 03-recruitment.sh | 89 | 0 |
| 合计 | 289 | 0 |

同一轮还通过了 `cd backend && mvn -q -DskipTests package` 和 `cd frontend && pnpm build`。
