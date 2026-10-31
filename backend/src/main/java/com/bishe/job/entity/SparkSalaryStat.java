package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 城市与技术方向薪资统计，对应 spark_salary_stat。
 */
@Data
@TableName("spark_salary_stat")
public class SparkSalaryStat {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String batchNo;
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
    private Integer isLatest;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
