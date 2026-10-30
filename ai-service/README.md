# 高校就业推荐平台 - AI 算法与智能体服务 (FastAPI)

本项目为毕业设计《基于Spark与RAG的高校就业推荐平台的设计与实现》中的 **AI 算法与多角色智能体服务**，基于 FastAPI 搭建，提供高性能异步接口与 SSE (Server-Sent Events) 流式输出，协同 Spring Boot 业务端（8080 端口）与 Vue 前端（5173 端口）。

---

## 1. 架构与功能模块

1. **基础业务与统一协议**：
   - 统一 JSON 响应格式 `{code, msg, data}`（与 Spring Boot 后端 `Result` 严格对齐，`code=200` 为成功）；
   - 全局异常拦截器统一捕获业务异常与系统错误。
2. **PySpark 离线分析与机器学习 (`/spark`)**：
   - 招聘数据清洗、薪资回归模型训练、统计聚合指标回写 MySQL。
3. **协同过滤与内容匹配推荐 (`/recommend`)**：
   - User-CF (基于学生行为矩阵的协同过滤) 与基于技能标签的内容匹配，输出综合岗位推荐与技能雷达图维度。
4. **RAG 向量知识库 (`/rag`)**：
   - 基于 Chroma 与 LangChain，向量化存储就业政策、校招面经、行业图谱，支持语义检索。
5. **多角色智能体与 SSE 流式推送 (`/agent`)**：
   - 针对学生、企业、管理员提供求职辅导与咨询问答；
   - 采用 Server-Sent Events (SSE) 协议，逐段输出思考过程与生成内容，以 `[DONE]` 结束。

---

## 2. 目录结构

```
ai-service/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口、CORS、全局异常与路由挂载
│   ├── api/                       # API 路由层
│   │   ├── __init__.py
│   │   ├── health.py              # GET /health 健康检查接口
│   │   ├── spark.py               # GET /spark 离线计算与任务状态
│   │   ├── recommend.py           # GET /recommend 岗位推荐与技能雷达
│   │   ├── rag.py                 # GET /rag 知识库向量检索
│   │   └── agent.py               # GET /agent 与 GET /agent/stream-demo (SSE)
│   ├── core/                      # 核心基础设施
│   │   ├── __init__.py
│   │   ├── config.py              # Pydantic-settings 配置管理
│   │   └── response.py            # 统一 Result 响应封装与全局异常处理
│   └── services/                  # 业务算法与逻辑实现层 (占位与业务逻辑)
│       ├── __init__.py
│       ├── spark_service.py       # Spark 离线计算任务调度
│       ├── recommend_service.py   # 协同过滤与推荐算法
│       ├── rag_service.py         # Chroma 向量库检索
│       └── agent_service.py       # LangChain 智能体与流式生成
├── .env.example                   # 环境变量配置示例模板
├── .env                           # 本地环境变量配置
├── requirements.txt               # Python 依赖清单
└── README.md                      # 项目说明文档
```

---

## 3. 运行环境

- **Python 虚拟环境**：`/workspace/bishe/.venv`
- **数据库**：MariaDB 11.8 (兼容 MySQL) 于 `127.0.0.1:3306`，库名 `job_platform`，账号 `job/job123`
- **向量数据库**：Chroma（本地目录 `./data/chroma`）
- **CORS 跨域**：默认允许 `http://localhost:5173` 与 `http://localhost:8080`

---

## 4. 启动命令

在项目根目录下，直接使用已有的虚拟环境运行 uvicorn：

```bash
/workspace/bishe/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

开发调试热重载模式：

```bash
/workspace/bishe/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 5. 接口测试与验证

### (1) 健康检查 (`/health`)

```bash
curl http://127.0.0.1:8000/health
```

返回示例：
```json
{
  "code": 200,
  "msg": "Service is healthy and ready",
  "data": {
    "status": "UP",
    "service": "ai-service",
    "env": "development",
    "port": 8000
  }
}
```

### (2) Agent SSE 流式对话演示 (`/agent/stream-demo`)

```bash
# 方式 1：默认测试
curl -N http://127.0.0.1:8000/agent/stream-demo

# 方式 2：自定义中文问题（使用 -G 与 --data-urlencode 防止 URL 编码异常）
curl -N -s -G --data-urlencode "q=请推荐适合计算机专业应届生的就业方向" http://127.0.0.1:8000/agent/stream-demo
```

返回输出为符合 SSE 规范的流式文本，例如：
```
data: {"step": 1, "role": "student", "thought": "正在意图识别与解析用户问题...", "content": "..."}

data: {"step": 2, "role": "student", "thought": "正在调用 RAG 知识库检索校招政策与高频面试要点...", "content": "..."}

data: {"step": 3, "role": "student", "thought": "正在调用 Spark / 推荐引擎结合上下文生成建议...", "content": "..."}

data: {"step": 4, "role": "student", "thought": "智能体总结完成", "content": "..."}

data: [DONE]
```

### (3) 其他模块接口

- **Spark 模块状态**：`curl http://127.0.0.1:8000/spark/status`
- **Spark 离线任务列表**：`curl http://127.0.0.1:8000/spark/jobs`
- **岗位推荐接口**：`curl http://127.0.0.1:8000/recommend/jobs?student_id=1`
- **技能雷达图接口**：`curl http://127.0.0.1:8000/recommend/radar?student_id=1`
- **RAG 知识检索接口**：`curl "http://127.0.0.1:8000/rag/search?q=校招政策"`
- **Swagger API 文档**：浏览器访问 `http://localhost:8000/docs`
