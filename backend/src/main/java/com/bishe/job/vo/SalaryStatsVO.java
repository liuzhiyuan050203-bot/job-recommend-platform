package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Data
public class SalaryStatsVO {

    private List<SalaryStatItemVO> records = new ArrayList<>();
    private List<SalaryStatItemVO> byDirection = new ArrayList<>();
    private List<SalaryStatItemVO> byCity = new ArrayList<>();

    @Data
    public static class SalaryStatItemVO {
        private String province;
        private String city;
        private String techDirection;
        private Integer jobCount;
        private BigDecimal avgSalary;
        private BigDecimal medianSalary;
        private BigDecimal minSalary;
        private BigDecimal maxSalary;
        private BigDecimal p25Salary;
        private BigDecimal p75Salary;
    }
}
