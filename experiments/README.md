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

## 1. 薪资预测严谨性

脚本：`experiments/salary/{prepare_real_salary,export_platform_jobs,run_salary_experiment}.py`  
数据说明：`data/REAL_DATA.md`（公开 MIT 数据集）与 `data/real_salary/`。

**核心结论**：演示/校招库里的月薪是按方向×城市公式**估算**的，不是官网真值。在估算标签上模型可做到 R²≈0.97–0.999，属于记忆生成公式，**不能**作为论文主结果。公开真实月薪上，最优测试 R² 约 **0.49–0.56**。

### 1.1 协议

- 80/20 holdout（seed=42）+ 训练集 5 折 CV；Ridge/Lasso 的 λ∈{0.01,…,1000} 按 CV 平均 R² 选取。
- 模型：LinearRegression、Ridge、Lasso、RandomForest（100 树）、GBT（80 轮）；另报 MeanBaseline。
- 特征：城市/方向 one-hot、city_tier、edu_years、exp_years；合成/校招另加 job_type；真实数据另加公司规模；可选 jieba→CountVectorizer+IDF 文本。

### 1.2 各数据集最优测试结果（完整表见 `results/salary_metrics.csv`）

| 数据集 | 行数 | 最优模型 / 特征 | 测试 R² | RMSE | MAE | CV R² |
|--------|------|-----------------|---------|------|-----|-------|
| synthetic（公式标签） | 3200 | GBT / base+jobtype | 0.973 | 1581 | 724 | 0.980±0.004 |
| campus_estimated（**非真值**） | 1758 | GBT / base+jobtype+text | 0.999 | 86 | 14 | 0.985±0.013 |
| BOSS 2023（MIT） | 9269 | GBT / base+company+text | **0.559** | 5394 | 3619 | 0.205±0.484* |
| 51job 2018（MIT） | 40896 | GBT / base+company+text | **0.493** | 4868 | 3326 | 0.485±0.013 |
| pooled_real + data_year | 50165 | RF / base+year | **0.372** | 5616 | 3923 | 0.354±0.019 |

\*BOSS 上 GBT 的 CV 方差大，同特征 RF 测试 R²=0.551、CV 0.519±0.046 更稳，生产选用 RF。

![r2](figures/salary_r2_best.png)
![rf](figures/salary_rf_compare.png)

### 1.3 生产模型

`ai-service/app/spark/salary_model.py` 仍用 **PySpark MLlib RandomForest**，训练改为 `pooled_real`（BOSS+51job），特征含 `data_year`（预测时固定 2023）。网格预测与 `/public/stats/salary/predict` API 不变。指标文件注明 `trainSource=pooled_real` 与「平台职位薪资为估算」。

---

## 3. Spark 扩展性（进行中）

## 4. RAG 混合检索与评测

脚本：`experiments/rag_eval/run_rag_eval.py`；题集 `questions.jsonl`（50+5）；校验 `validate_questions.py`。  
生产：`ai-service/app/rag/{bm25,rerank,store,chunking}.py`，默认 `RAG_RETRIEVAL_MODE=hybrid`（Markdown 标题切分仍为生产入库方式）。

| 切分 | 检索 | Hit@1 | Hit@3 | Hit@5 | MRR@10 | 平均 ms | P95 ms | 无关拒答 |
|------|------|------:|------:|------:|-------:|--------:|-------:|---------:|
| 定长 | dense | 0.72 | 0.86 | 0.94 | 0.804 | 11.2 | 20.0 | 1.0 |
| 定长 | bm25 | 0.84 | 0.96 | 0.96 | 0.900 | 7.7 | 20.6 | 1.0 |
| 定长 | hybrid | 0.86 | 0.96 | 0.98 | 0.913 | 17.1 | 29.2 | 1.0 |
| 定长 | hybrid+rerank | 0.92 | 1.00 | 1.00 | 0.960 | 1863 | 2371 | 1.0 |
| **标题** | dense | 0.80 | 0.92 | 0.96 | 0.870 | 13.9 | 24.8 | 1.0 |
| 标题 | bm25 | 0.82 | 0.94 | 0.98 | 0.886 | 4.9 | 14.3 | 1.0 |
| **标题** | **hybrid** | **0.92** | 0.96 | **1.00** | **0.947** | **15.0** | 25.0 | 1.0 |
| 标题 | hybrid+rerank | 0.92 | 1.00 | 1.00 | 0.957 | 1861 | 2060 | 1.0 |

默认选标题切分 + hybrid：与 rerank 同级 Hit@1，延迟约 15ms；rerank 平均 1.86s > 1.5s 阈值，不作默认。`tests/api/06-rag.sh` PASS=92。

![hit](figures/rag_eval_hit.png)
![lat](figures/rag_eval_latency.png)

---

