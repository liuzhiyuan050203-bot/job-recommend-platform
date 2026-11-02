# 批任务与在线问答的 CPU 争用：定位与修复

所有数字来自本目录脚本在同一台 8 vCPU 机器上的真实运行（2026-11-02，时间为 UTC+8），原始输出在 `experiments/results/stability_*.json(l)`。

## 1. 现象

`bash tests/run-all.sh` 平时 661/0，偶发一次 657/5：`tests/api/06-rag.sh` 里企业端 SSE 问答 180 s 超时。
同一时刻 `05-recommend.sh` 触发的 Spark 推荐批次跑了约 269 s（平时约 121 s），两段完全重叠。

## 2. 根因

| 证据 | 结论 |
|------|------|
| 批次期间对 `/health` 采样 644 次：p50 2.2 ms，p99 12.5 ms，max 29.5 ms | FastAPI 事件循环没有被阻塞 |
| `ollama.log`：空闲解码约 19 tok/s；批次期间降到 0.54–3.19 tok/s；超时那次 161 token 用了 188 s（约 1176 ms/token） | 慢在大模型解码 |
| `llama-server` 启动参数为 `-t 8`；Spark 使用 `local[*]`（8 核），两者优先级相同 | llama.cpp 的 8 个线程与 Spark 的 8 个任务线程争抢 8 个核；llama.cpp 每个 token 都要等所有线程同步，只要一个线程被抢占，整步就被拖慢，所以速度不是减半，而是直接崩到 1 tok/s 以下 |
| 服务端没有回答截止时间；token 一个个慢慢往外吐，8 s 心跳从未触发 | 客户端最终在 180 s 处超时，拿不到 `done` |
| `05-recommend.sh` 只提交批次不等待，`06-rag.sh` 紧接着就开始 | 测试本身不确定：是否重叠取决于机器快慢 |

## 3. 修复

1. **批次隔离**（`ai-service/app/spark/runner.py`、`batch_worker.py`）：推荐和分析批次在独立子进程中运行，子进程及其 Spark JVM 以 `nice 10` 启动（`SPARK_BATCH_NICE`），通过进程组可以超时终止（`SPARK_BATCH_TIMEOUT`）。ai-service 停止时会终止正在运行的批次，并在 `spark_task_log` 中记为失败（"ai-service 停止，批次被终止"）。每个批次的日志写到 `logs/spark-batch/<batch>.log`。
2. **队列与锁**：同一时间只运行一个批次。运行期间再提交的批次进入 FIFO 队列（最多 `SPARK_BATCH_QUEUE_MAX=2` 个），与已排队批次任务组合相同的提交会合并（`merged=true`），队列满时返回 409。用 `fcntl` 文件锁（`/tmp/bishe-spark-batch.lock`）和命令行 `run_all` 互斥。`/spark/status` 的 `batchQueue` 字段给出 current、queued、master 和 nice；`/spark/tasks/{batch}` 返回 `state`（QUEUED、RUNNING 或 FINISHED）。管理端在提交被排队时会提示"已排队"。
3. **Spark 限核**（`session.py`）：`local[*]` 改写为 `local[min(SPARK_LOCAL_CORES, 核数)]`，默认值为 4。显式写的 `local[N]` 或 `spark://` 不受影响，集群模式仍由 `spark.cores.max` 控制。
4. **Ollama 线程**（`scripts/start-ollama.sh`）：`OLLAMA_NUM_THREAD=auto` 时取核数减 2（8 核机器为 6），把它写入模型参数 `num_thread`，对 `/v1` 兼容接口同样生效（实测 `llama-server -t 6`）。设为 `0` 则保持 Ollama 默认值。`LLAMA_ARG_THREADS` 环境变量不起作用，因为 Ollama 会显式传 `-t`。
5. **服务端超时降级**（`ai-service/app/agent/chat.py`）：超过首 token 等待上限（`LLM_FIRST_TOKEN_TIMEOUT=45` s），或整轮回答超过截止时间（`LLM_ANSWER_DEADLINE=90` s）时，停止等待大模型：
   - RAG 问答改用知识库原文摘录作答，带 `[n]` 引用；
   - 工具类问答直接用工具结果作答；
   - `done` 事件带 `degraded: "llm_timeout"`，并以"【降级回答】大模型响应超时"开头。
   这两个时间都远小于后端和测试的 180 s 上限，因此客户端总能收到 `done`。
6. **测试确定性**：
   - `05-recommend.sh` 等待自己触发的批次结束（最长 900 s），并断言批次成功、日志记录了 Spark master、推荐统计切换到了新批次；
   - `06-rag.sh` 开始前等待 Spark 空闲；
   - 共用函数在 `tests/api/lib.sh` 中（`wait_spark_batch`、`wait_spark_idle`）。

## 4. 结果

### 4.1 批次运行时 Ollama 的解码速度（`ollama_under_spark.sh`，直连 `/api/generate`，64 token）

| 配置 | 8 线程 tok/s | 6 线程 | 4 线程 | 批次耗时 |
|------|-------------|--------|--------|----------|
| 改造前：`local[*]`，nice 0 | 3.0、0.4（第二次 64 token 用时约 160 s） | 8.81、7.15 | 4.77、9.28 | 273 s |
| 改造后：`local[4]`，nice 10（每种线程数测 9–10 次） | 均值 15.6（13.67–18.09） | **均值 17.5（16.44–18.58）** | 均值 13.45（12.63–13.83） | 216 s |

空闲时的对照值：8 线程 19.9 和 21.8，6 线程 18.0，4 线程 12.8 和 13.4。
改造后，批次运行期间 6 线程基本达到空闲水平。批次本身也变快了，因为减少了与大模型的互相抢占。

### 4.2 端到端：批次运行期间三种角色同时提问（`stress_chat_during_batch.py`，经后端 SSE）

问题依次为：学生"三方协议怎么签？"、企业"列出我发布的职位"、管理员"哪个城市岗位最多"。

| 场景 | 完成 / 提问 | 客户端超时 | 降级 | 首 token 中位 / 最大 (s) | 总耗时中位 / 最大 (s) | 批次耗时 |
|------|-----------|-----------|------|------------------------|---------------------|----------|
| 改造前，空闲 | 3/3 | 0 | – | 1.58 / 16.75（首问含模型加载） | 9.99 / 25.09 | – |
| 改造前，批次中（2 轮） | 5/6 | 1（企业问答 181.59 s 无 done） | – | 0.67 / 8.89 | 35.09 / 181.59 | 311 s |
| 改造后，空闲 | 3/3 | 0 | 0 | 1.80 / 9.33（首问含模型加载） | 15.77 / 17.59 | – |
| 改造后，批次中（2 轮） | 6/6 | 0 | 0 | 0.225 / 0.26 | 9.43 / 14.82 | 156.7 s |
| 改造后，批次中（8 轮，24 问全部落在批次内） | 24/24 | 0 | 0 | 0.215 / 6.96 | 8.55 / 18.69 | 259.1 s |

两种场景下事件循环都很健康，`/health` 的 p99 不超过 25 ms。两次批次的产出完全一致：26019 条输入，21420 条推荐。

把 `LLM_FIRST_TOKEN_TIMEOUT` 设为 0.3、`LLM_ANSWER_DEADLINE` 设为 1.5 做强制降级验证：学生问答返回知识库摘录并带 [1][2][4] 引用，企业问答返回职位列表，`done.degraded` 为 `llm_timeout`。

## 5. 复现

```bash
bash scripts/start-all.sh --no-frontend
.venv/bin/python experiments/stability/stress_chat_during_batch.py --label after_idle --no-batch --rounds 1
.venv/bin/python experiments/stability/stress_chat_during_batch.py --label after_batch --rounds 2
bash experiments/stability/ollama_under_spark.sh old 0 0 8 6 4    # 改造前资源配置（会真实写入一批推荐）
bash experiments/stability/ollama_under_spark.sh new 4 10 8 6 4   # 改造后默认配置
```
