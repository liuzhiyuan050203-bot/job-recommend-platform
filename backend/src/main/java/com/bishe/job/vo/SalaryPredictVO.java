package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

@Data
public class SalaryPredictVO {

    private String city;
    private String province;
    private String techDirection;
    private Integer education;
    private BigDecimal experienceYears;
    private List<String> skills;
    private Integer jobType;
    private BigDecimal predictedSalary;
    private BigDecimal ciLow;
    private BigDecimal ciHigh;
    private String modelVersion;
    private Map<String, Object> metrics;
    private String source;
}
