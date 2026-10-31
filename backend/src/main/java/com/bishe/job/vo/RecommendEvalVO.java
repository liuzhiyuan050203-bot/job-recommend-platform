package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 最近一批推荐评估。metrics 含 cf、content、hybrid、popular 在 K=5/10/20 的结果。
 */
@Data
public class RecommendEvalVO {

    private String batchNo;
    private String cfMethod;
    private BigDecimal alpha;
    private String fusion;
    private Boolean adaptiveAlpha;
    private Integer halfLifeDays;
    private String summary;
    private BigDecimal cosineNdcg10;
    private BigDecimal alsNdcg10;
    private List<RecommendMetricVO> metrics = new ArrayList<>();
}
