package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;

@Data
public class RegionPointVO {

    private String name;
    private Integer value;
    private String adcode;
    private Integer companyCount;
    private BigDecimal avgSalary;
    private Integer applyCount;
}
