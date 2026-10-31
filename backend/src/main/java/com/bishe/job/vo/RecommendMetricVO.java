package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;

/**
 * 某一算法在某个 K 上的离线指标。比例字段为 0 到 1。
 */
@Data
public class RecommendMetricVO {

    private String batchNo;
    private String algo;
    private Integer k;
    private BigDecimal precisionAtK;
    private BigDecimal recallAtK;
    private BigDecimal ndcgAtK;
    private BigDecimal coverage;
    private Integer userCount;
    private BigDecimal alpha;
    private String cfMethod;
}
