# Spark 扩展性压测（对比用，不改生产）

本目录脚本比较 **Pandas** 与 **PySpark `local[1/2/4/8]`** 在清洗、多维分位数聚合、隐式 ALS 上的墙钟时间与峰值 RSS。
**生产流水线（`ai-service/app/spark/` 的 clean / aggregate / salary_model / ALS / recommend）仍全部使用 PySpark**，本压测只回答「数据量多大时 Spark 相对 Pandas 开始划算」，不替换生产实现。

本机结果摘要：清洗任务在约 **100 万职位**时 Spark `local[4/8]` 任务时间反超 Pandas；ALS 在 `local[8]` 与 `implicit` 接近；聚合在单机上 Pandas 仍更快。详见 `experiments/README.md` §3。

```bash
.venv/bin/python data/generate_demo_data.py --scale 100000   # 或 1e4 / 5e5 / 1e6
.venv/bin/python experiments/scale/run_scale_bench.py
# 续跑大规格并合并已有 JSON：
.venv/bin/python experiments/scale/run_scale_bench.py --scales 500000 1000000 --merge
```
