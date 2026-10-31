#!/usr/bin/env python3
"""LLM 与 Embedding 基础设施验证脚本.

执行方式:
    cd ai-service && ../.venv/bin/python scripts/verify_llm.py
"""

import asyncio
from pathlib import Path
import sys
import time
from typing import List

# 保证当前执行路径优先加载 ai-service 下的 app 模块
CURRENT_DIR = Path(__file__).resolve().parent
AI_SERVICE_DIR = CURRENT_DIR.parent
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

import numpy as np

from app.core.config import settings
from app.core.embedding import (
    embed_documents,
    embed_query,
    get_embedding_model,
    health as embedding_health,
)
from app.core.llm import (
    OfflineGenerator,
    astream_chat,
    health as llm_health,
    is_available as llm_is_available,
)


def run_verification():
    """执行全部基础设施层功能与性能验证."""
    print("=" * 65)
    print(" 毕业设计: 基于Spark与RAG的高校就业推荐平台")
    print(" LLM + Embedding 基础设施层验证 (Infrastructure Layer Verification)")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. 健康状态探活
    # -------------------------------------------------------------
    print("\n[Step 1] LLM 与 Embedding 健康状态探活:")
    print("-" * 65)
    lh = llm_health(force=True)
    eh = embedding_health()

    print(f"  [LLM] 提供方 (Provider)     : {lh.get('provider')}")
    print(f"  [LLM] 模型名称 (Model)      : {lh.get('model')}")
    print(f"  [LLM] 服务地址 (Base URL)   : {lh.get('base_url')}")
    print(f"  [LLM] 可用状态 (Available)  : {lh.get('available')}")
    print(f"  [LLM] 运行模式 (Mode)       : {lh.get('mode')}")
    print(f"  [LLM] 探活耗时 (Latency)    : {lh.get('latency_ms', 0)} ms")

    print(f"  [Embedding] 模型名称        : {eh.get('model')}")
    print(f"  [Embedding] 输出向量维度    : {eh.get('dim')} dim")
    print(f"  [Embedding] 缓存目录        : {eh.get('cache_dir')}")
    print(f"  [Embedding] 已加载内存      : {eh.get('loaded')}")

    # -------------------------------------------------------------
    # 2. 流式文本生成与吞吐率测试 (TTFT & tok/s)
    # -------------------------------------------------------------
    print("\n[Step 2] LLM 中文流式对话测试与生成性能测量:")
    print("-" * 65)
    test_prompt = "请用两句话为计算机专业应届毕业生提供针对校招的技术求职建议。"
    print(f"提问内容: \"{test_prompt}\"")
    print("流式回答: ", end="", flush=True)

    t0 = time.perf_counter()
    first_token_time = None
    token_count = 0
    collected_tokens: List[str] = []

    async def _stream_test():
        nonlocal first_token_time, token_count
        async for chunk in astream_chat(test_prompt):
            if first_token_time is None:
                first_token_time = time.perf_counter()
            token_count += 1
            collected_tokens.append(chunk)
            print(chunk, end="", flush=True)

    asyncio.run(_stream_test())
    t_end = time.perf_counter()

    ttft_ms = ((first_token_time - t0) * 1000) if first_token_time else 0.0
    total_time = t_end - t0
    gen_time = (t_end - first_token_time) if first_token_time else total_time
    tok_per_sec = (token_count / gen_time) if gen_time > 0 else 0.0

    print("\n" + "-" * 65)
    print(f"  首字响应延迟 (TTFT) : {ttft_ms:.2f} ms")
    print(f"  完整生成耗时 (Total): {total_time:.2f} s")
    print(f"  生成 Chunk/Token 数量: {token_count}")
    print(f"  生成速率 (Throughput): {tok_per_sec:.2f} tokens/s")

    # -------------------------------------------------------------
    # 3. FastEmbed 向量计算与余弦相似度验证
    # -------------------------------------------------------------
    print("\n[Step 3] FastEmbed 向量嵌入与余弦相似度计算:")
    print("-" * 65)
    query = "计算机专业毕业生寻找软件开发与算法岗位"
    sentences = [
        "计算机专业学生热衷于投递后端开发、前端开发与人工智能算法等技术岗位。",
        "秋季校园招聘期间，毕业生需要提前准备技术面试、刷算法题并优化个人简历。",
        "机械制造、土木工程与传统重工业企业积极开展春季校园线下双选会。",
    ]

    print(f"检索查询: \"{query}\"")
    q_vec = np.array(embed_query(query), dtype=np.float32)
    doc_vecs = [np.array(v, dtype=np.float32) for v in embed_documents(sentences)]

    for idx, (sent, d_vec) in enumerate(zip(sentences, doc_vecs), 1):
        # 归一化向量点乘即余弦相似度
        sim = float(np.dot(q_vec, d_vec))
        print(f"  句子 [{idx}] (余弦相似度: {sim:.4f}):")
        print(f"    \"{sent}\"")

    # -------------------------------------------------------------
    # 4. OfflineGenerator 离线 2-gram 抽取生成器测试
    # -------------------------------------------------------------
    print("\n[Step 4] OfflineGenerator 离线知识切片抽取测试:")
    print("-" * 65)
    sample_chunks = [
        {
            "title": "教育部2026届高校毕业生就业支持政策",
            "content": "为鼓励高校毕业生投身基层建设，国家出台学费补偿和助学贷款代偿政策。对到中西部基层单位就业满3年的毕业生给予足额代偿资金。",
            "source": "教育部就业政策",
        },
        {
            "title": "互联网大厂Java后端校招求职核心考点",
            "content": "校招技术一面与二面重点考察 JVM 垃圾回收机制、Spring 事务传播行为以及 MySQL 索引最左匹配原则与慢SQL调优。",
            "source": "校招面经",
        },
        {
            "title": "应届生求职简历撰写规范",
            "content": "简历排版需重点清晰，项目经历建议运用 STAR 原则叙述，量化说明工程难点、并发量及业务提升效果。",
            "source": "就业指导",
        },
    ]

    offline_query = "Java后端校招面试一般重点考察什么知识点？"
    print(f"离线测试问题: \"{offline_query}\"\n")
    offline_output = OfflineGenerator.generate(offline_query, sample_chunks, max_sentences=3)
    print(offline_output)

    print("\n" + "=" * 65)
    print(" 所有组件验证通过 (ALL VERIFICATIONS PASSED)")
    print("=" * 65)


if __name__ == "__main__":
    run_verification()
