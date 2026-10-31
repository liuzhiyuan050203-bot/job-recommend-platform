package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class StatsOverviewVO {

    private long jobCount;
    private long companyCount;
    private long studentCount;
    /** 未删除的投递总数，供首页和管理员看板复用 */
    private long applicationCount;
    private BigDecimal avgSalary;
    private long cityCount;
    private String lastBatchNo;
    private LocalDateTime lastSuccessTime;
}
