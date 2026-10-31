package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class StatsOverviewVO {

    private long jobCount;
    private long companyCount;
    private long studentCount;
    private BigDecimal avgSalary;
    private long cityCount;
    private String lastBatchNo;
    private LocalDateTime lastSuccessTime;
}
