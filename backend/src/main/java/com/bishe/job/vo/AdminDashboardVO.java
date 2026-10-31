package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 管理员看板摘要：平台计数、最近成功的 Spark 批次、推荐 NDCG 与 AI 使用量。
 */
@Data
public class AdminDashboardVO {

    private StatsOverviewVO platform;
    private SparkBrief spark = new SparkBrief();
    private RecommendBrief recommend = new RecommendBrief();
    private AiUsage ai = new AiUsage();

    @Data
    public static class SparkBrief {
        private String batchNo;
        private String taskCode;
        private String taskName;
        private Integer status;
        private LocalDateTime endTime;
    }

    @Data
    public static class RecommendBrief {
        private String batchNo;
        private BigDecimal ndcgAt10;
        private BigDecimal coverage;
        private Long userCount;
        private Long recommendCount;
        private String cfMethod;
        private BigDecimal alpha;
    }

    @Data
    public static class AiUsage {
        private long sessionCount;
        private long messageCount;
    }
}
