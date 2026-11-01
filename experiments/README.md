# 实验章节素材（可复现）

所有数字均来自本目录脚本的真实运行，原始输出在 `results/`，图在 `figures/`。
**生产流水线仍使用 PySpark**（清洗 / 聚合 / 薪资回归 / ALS / 推荐离线任务）；本目录的 Pandas 对比只用于扩展性压测。

```bash
export PATH=$HOME/.local/bin:$PATH
# 分项复现（各一条命令）
.venv/bin/python experiments/salary/run_salary_experiment.py --folds 5
.venv/bin/python experiments/recommend/run_recommend_ablation.py --seeds 5
.venv/bin/python experiments/scale/run_scale_bench.py
.venv/bin/python experiments/rag_eval/run_rag_eval.py
```

---

## 2. 推荐算法消融

脚本：`experiments/recommend/run_recommend_ablation.py`  
数据：库内合成行为（`data/generate_demo_data.py`，方向+城市偏好）及对照变体 `pop_noise`（25% 内容偏好 / 50% Zipf 热度 / 25% 均匀）。  
协议：正样本=收藏/投递；每人留出 20%；`random` 重复 5 个种子报 mean±std；`time` 为生产所用的按时间留出（单次）。融合 α 在**训练内验证集**上按 NDCG@10 选择，测试集只报告一次。

### 2.1 主结果（original 行为，random，45 天衰减）

| 方法 | P@10 | R@10 | NDCG@5 | NDCG@10 | NDCG@20 | Cov@10 |
|------|------|------|--------|---------|---------|--------|
| Popularity | 0.0049±0.0008 | 0.0226±0.0057 | 0.0101±0.0040 | 0.0138±0.0048 | 0.0159±0.0050 | 0.004 |
| UserCF(cosine) | 0.1263±0.0047 | 0.5086±0.0204 | 0.4560±0.0164 | 0.4757±0.0176 | 0.4873±0.0189 | 0.171 |
| ALS（生产默认 rank=8） | 0.0717±0.0025 | 0.2951±0.0121 | 0.1914±0.0086 | 0.2233±0.0077 | 0.2454±0.0082 | 0.094 |
| ALS(val-tuned) | 0.1296±0.0065 | 0.5235±0.0303 | 0.4403±0.0292 | 0.4688±0.0298 | 0.4846±0.0261 | 0.238 |
| Content | 0.0916±0.0045 | 0.3673±0.0188 | 0.2790±0.0132 | 0.3131±0.0154 | 0.3274±0.0137 | 0.235 |
| Hybrid(cosine, val-α) | **0.1323±0.0026** | **0.5331±0.0120** | **0.4671±0.0160** | **0.4931±0.0124** | **0.5117±0.0108** | 0.215 |
| Hybrid(ALS-tuned, val-α) | 0.1314±0.0060 | 0.5309±0.0276 | 0.4418±0.0328 | 0.4716±0.0345 | 0.4873±0.0306 | 0.240 |

![methods](figures/recommend_methods_original.png)

**CF vs ALS**：用户余弦在演示集上稳定优于默认 ALS；验证集网格（rank∈{8,32,64}×reg∈{0.1,1,10}×alpha∈{5,20,40}）后 ALS 可逼近余弦（NDCG@10 0.469 vs 0.476），仍略低且无因子用户无法在线推断。生产因此用用户余弦做协同过滤，ALS 留在离线任务中作对照（`ai-service/app/spark/recommend.py`）。

### 2.2 α 扫描（测试集敏感性，非选型依据）

![alpha](figures/recommend_alpha_sweep_original.png)

余弦融合在 α≈0.4–0.6 达峰；纯内容（α=0）与纯协同（α=1）均低于混合。生产 α 由留出集自动选择（常见 0.4–0.7）。

### 2.3 时间衰减 / 学历惩罚消融

| 设置 | Hybrid(cosine) NDCG@10 (random) | 同方法 (time) |
|------|----------------------------------|---------------|
| 45 天衰减 + 学历×0.35（生产） | 0.4931±0.0124 | **0.3596** |
| 无衰减 + 学历×0.35 | 0.5191±0.0189 | 0.3245 |
| 45 天衰减 + 无学历惩罚 | 0.5165±0.0168 | 0.3730 |

按时间留出时，45 天衰减明显更好（0.360 vs 0.325），与生产协议一致；随机留出下无衰减略高，因合成时间近似均匀。去掉学历惩罚在本合成行为上略升（生成器未把学历不匹配写入负反馈），生产仍保留 0.35 作为业务约束。

### 2.4 冷启动（随机抽 20% 学生）

| 场景 | 最佳方法 | NDCG@10 |
|------|----------|---------|
| full（删光行为） | Content | 0.2714±0.0351 |
| full | Hybrid 兜底 0.75C+0.25P | 0.2391±0.0157 |
| fewshot3（保留 3 条） | Hybrid(α=0.5, adaptive) | **0.3212±0.0209** |

无行为时协同过滤失效，内容匹配是主信号；少量行为后自适应融合超过纯内容。

### 2.5 合成行为偏差（pop_noise 对照）

在弱偏好行为上，**Popularity NDCG@10=0.1763±0.0087 最高**，Content 降至 0.037，Hybrid/UserCF ≈0.17。说明原生成器的「方向+城市」聚集会抬高内容与混合指标；论文需如实写明演示数据偏差，并把 pop_noise 作为压力测试。

原始表：`results/recommend_*_{summary,alpha_sweep,coldstart}.csv`，汇总 JSON：`results/recommend_ablation.json`。

---

## 1. 薪资预测（进行中，见 salary_run.log）

## 3. Spark 扩展性（进行中）

## 4. RAG 混合检索（进行中）
