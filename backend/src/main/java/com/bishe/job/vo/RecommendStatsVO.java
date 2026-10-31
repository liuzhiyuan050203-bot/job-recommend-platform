package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;

/**
 * 当前生效推荐批次的覆盖情况。coverage 为推荐职位去重数 / 在架职位数。
 */
@Data
public class RecommendStatsVO {

    private String batchNo;
    private Long userCount;
    private Long recommendCount;
    private Long positionCount;
    private Long catalogSize;
    private BigDecimal coverage;
    private String cfMethod;
    private BigDecimal alpha;
}
