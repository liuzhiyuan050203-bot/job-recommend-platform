package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 薪资回归网格预测，对应 spark_salary_predict。
 */
@Data
@TableName("spark_salary_predict")
public class SparkSalaryPredict {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String batchNo;
    private Long userId;
    private Long positionId;
    private String province;
    private String city;
    private String techDirection;
    private Integer education;
    private BigDecimal experienceYears;
    private BigDecimal predictedSalary;
    private BigDecimal ciLow;
    private BigDecimal ciHigh;
    private String modelVersion;
    private String featureJson;
    private Integer isLatest;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
