package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;

/**
 * 仪表盘 SQL 聚合行。label 为月份或技能名，total 为计数，avgLevel 为平均熟练度。
 */
@Data
public class DashboardAggVO {

    private String label;
    private Long total;
    private BigDecimal avgLevel;
}
