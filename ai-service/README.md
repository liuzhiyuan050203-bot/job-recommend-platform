# 高校就业推荐平台 - AI 算法与智能体服务

本目录是毕业设计《基于Spark与RAG的高校就业推荐平台的设计与实现》的算法与智能体服务。FastAPI 提供 Spark 离线分析、混合推荐、RAG 知识库和三类角色助手。Spring Boot（8080，上下文 `/api`）通过内部令牌调用本服务，Vue 前端不直接访问 8000 端口。

## 1. 运行

```bash
cd /workspace/bishe/ai-service
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

依赖见 `requirements.txt`。虚拟环境为仓库根目录的 `.venv`。MariaDB `job_platform`（`job` / `job123`）和本地 Ollama（`http://127.0.0.1:11434/v1`，模型 `qwen2.5:3b`）需已启动。默认模型大约 19 token/s 生成、150 token/s 处理提示词，因此提示词控制在约 1500 字，回答 `max_tokens` 为 500，检索默认 4 个切片、每段最多 300 字。

重建知识库（会清空 Chroma 集合和 `rag_document` 后全量写入）：

```bash
cd /workspace/bishe/ai-service
../.venv/bin/python -m app.rag.ingest --all
```

只增量更新某一来源：`--source knowledge|cms|jobs|uploads`。加上 `--rebuild` 会先删除该来源的旧切片。内容哈希未变化的文档会跳过向量计算。

## 2. RAG 设计

### 来源

| 来源 | `source_type` | `doc_key` | 说明 |
| --- | --- | --- | --- |
| `data/knowledge/*.md` | 4 知识库文件 | `kb:文件名` | 政策、简历、面试、三方、档案、劳动合同、校招、平台指南、面经、企业须知 |
| `cms_article` | 2 公告同步 / 3 政策同步 | `cms:{id}` | `status=1 AND deleted=0`。类型 1 双选会、3 新闻为公告同步；类型 2 政策为政策同步 |
| `job_position` | 5 职位同步 | `job:{id}` | 已上架、审核通过、未删除。正文含标题、公司、城市、薪资、技能、职责 |
| `ai-service/data/uploads/` | 6 管理员上传 | `upload:文件名` | 管理接口上传的 `.md` / `.txt` |

`doc_type`：1 就业政策，2 平台使用指南，3 面经精选，4 企业招聘须知，5 求职指导，6 手续 FAQ，7 职位信息。正文短于 8 个字的公告不入库。

### 切片与向量

Markdown 先按 `#` / `##` / `###` 分节，再按约 400 字、重叠 60 字切开。分隔符顺序接近 `RecursiveCharacterTextSplitter`：空行、换行、。！？；，、、空格，最后才硬切。写入向量的文本会加上「标题 / 章节」前缀，库里的 `content` 仍是切片正文。

Chroma 使用 `PersistentClient`，目录为 `settings.CHROMA_DIR`（默认 `ai-service/data/chroma`，已 gitignore），集合名 `job_knowledge`，空间为 cosine。嵌入模型是 FastEmbed `BAAI/bge-small-zh-v1.5`（512 维，查询走 `query_embed`）。元数据包含 `rag_doc_id`、`doc_type`、`source_type`、`source_id`、`title`、`section`、`chunk_no`、`doc_key`、`ref`。

MySQL `rag_document` 一行对应一个切片。`content_hash` 是标题、章节和正文的 SHA-256。重索引时若同一 `doc_key` 的哈希序列未变且已入库，则跳过；否则按 `doc_key` **物理删除**旧的 Chroma 向量和 MySQL 行再写入，不做逻辑删除，避免职位全量重建留下历史垃圾行。下架或不再出现的职位、删掉的知识库文件会在对应来源索引时剪掉。

### 检索与引用

`retrieve(query, top_k=4, doc_types, score_threshold)` 的分数是 `1 - cosine distance`。默认阈值 `RAG_SCORE_THRESHOLD=0.50`：政策类相关问句大约 0.65 以上，无关问句（午饭、天气、量子计算）大约 0.30–0.45，因此无关问题返回空列表。职位问句只在职位意图下检索 `doc_type=7`。

没有切片超过阈值时，助手直接说明知识库没有相关资料，不把问题交给模型自由发挥。有切片时，提示词把它们编成 `[1]`…`[n]`，并要求句末引用。若模型漏标，服务端会补一段「参考来源」。没有切片时，提示词明确禁止 `[1]`、`[2]`；无论有没有切片，流式输出都会丢掉编号大于资料条数的 `[n]`。末尾没写完的 `[` 先留在缓冲区，避免把半个标记拆进两个 delta。`done.answer` 等于已经推送给前端的文字。响应里始终有结构化 `sources` 事件。

### 管理接口（需内部令牌）

- `GET /rag/admin/documents`：按 `doc_key` 分组分页
- `GET /rag/admin/stats`
- `POST /rag/admin/upload`：multipart，字段 `file`、`title`、`doc_type`
- `POST /rag/admin/reindex?source=knowledge|cms|jobs|uploads|all` 或 `?doc_key=kb:就业政策.md`
- `DELETE /rag/admin/documents?doc_key=`：同时删掉 `upload:` 文档留在 `data/uploads/` 的正文和 meta，避免按 uploads 重建时又入库
- `GET /rag/search?q=`：调试检索

`GET /rag` 与 `GET /rag/status` 只返回规模，不要求令牌。

## 3. 三类助手

| 角色头 | 助手 | 工具 |
| --- | --- | --- |
| `student` | 学生就业助手 | `search_jobs`、`get_my_recommendations`（先读 `spark_recommend`，没有则实时推荐）、`predict_salary`、`analyze_resume_gap` |
| `company` | 企业招聘助手 | `generate_job_description`、`polish_job_description`、`screen_applicants`、`list_my_jobs` |
| `admin` | 管理员数据助手 | `salary_stats`、`tech_trend`、`region_distribution`、`city_distribution`、`recommend_eval`、`platform_overview` |

工具里的 `user_id` / `role` 只来自请求头，并与 `sys_user` 核对。学生不能筛选候选人，也不能看全平台统计；企业只能筛选 `ent_company.user_id` 等于自己的职位。管理员统计是只读参数化 SQL，模型不能提交 SQL。`spark_*` 查询一律 `is_latest=1 AND deleted=0`。

### 路由

`LLM_TOOL_CALLING=auto` 且基址在本机，或模型名里参数量不超过 8B 时，使用关键词和槽位（城市、方向、学历、年限、职位编号、技能）做确定性路由，避免 3B 模型漏调工具。槽位词典来自 `app/spark/dicts.py` 和库里的技术方向、技能标签。`LLM_TOOL_CALLING=true` 时先用 LangChain `bind_tools`，没有合法工具调用再退回同一套路由。工具结果压成短文本后，由模型流式写最终回答。模型不可用时走【离线模式】：工具结果渲染成列表，知识库用 `OfflineGenerator` 做摘录。

政策类问题排除职位切片；找岗位时检索职位切片，并以 SQL 工具结果为准。

管理员问「哪个城市岗位最多」「城市分布」时调用 `city_distribution(top_n)`：对已审核、已上架、未删除的 `job_position` 按 `city, province` 计数。问省份、地区分布或热力图仍用 `region_distribution`（`spark_region_dist`）。两者都对不上，也不像薪资、趋势、评估或平台概况时，改为调用 `platform_overview`，并在就业政策、指南、面经、招聘须知、求职指导和手续 FAQ 上做检索，不再只要求用户换一种问法。

## 4. 流式协议

`POST /agent/chat/stream`，JSON：`{question, history:[{role,content}], session_id?}`。

请求头：`X-Internal-Token`、`X-User-Id`、`X-User-Role`（`student` / `company` / `admin`）。

`Content-Type: text/event-stream`，每条为 `data: <json>\n\n`，`json` 含 `type`：

| type | 内容 |
| --- | --- |
| `meta` | `role`、`agent`、`mode`（online/offline）、`model`、`session_id` |
| `status` | `text`，如「正在检索知识库…」「正在调用工具 search_jobs…」 |
| `tool` | `name`、`args`、`summary` |
| `sources` | `items`: `index,title,doc_type,source_type,source_id,section,score,snippet` |
| `delta` | `text` |
| `error` | `msg` |
| `done` | `answer`、`sources`、`tools`、`latency_ms`、`first_token_ms` |

结束后发送 `data: [DONE]`。等待超过约 8 秒会发注释行 `: ping`。同步接口 `POST /agent/chat` 返回与 `done` 相同的 JSON，供测试使用。`GET /agent/stream-demo` 仍是原来的演示流，不查库、不校验令牌。会话和消息由 Spring Boot 写入 `ai_session` / `ai_message`，本服务只回传 `session_id`。

## 5. 内部令牌

`AI_INTERNAL_TOKEN` 与后端 `fastapi.internal-token` 使用同一默认值，比较用 `hmac.compare_digest`，日志不打印令牌。

必须带令牌的路径：`/agent/chat*`、`/rag/admin/*`、`/rag/search`、`/recommend/user/*`、`/recommend/jobs`、`/recommend/radar`、`/recommend/run`、`/spark/run`。缺少令牌返回 HTTP 401，令牌错误返回 HTTP 403。

保持公开：`/`、`/health`、`/docs`、`/ai/llm/health`、`/agent/stream-demo`、`/spark/tasks*`、`/spark/status`、`/recommend/similar/*`、`/recommend/eval`、`/recommend/status`。后端 `FastApiClient` 的全部请求都会带上该请求头，因此推荐、薪资预测和 Spark 任务提交仍可工作。

## 6. 目录补充

```
app/rag/          切片、Chroma/MySQL 存储、入库 CLI、检索
app/agent/        路由、工具、SSE 对话
app/core/security.py   内部令牌中间件
data/knowledge/   仓库根目录下的策展 Markdown
```

已有库升级表结构（不删业务数据）：

```bash
mariadb -h127.0.0.1 -ujob -pjob123 job_platform < /workspace/bishe/db/migrations/phase5_rag.sql
```
