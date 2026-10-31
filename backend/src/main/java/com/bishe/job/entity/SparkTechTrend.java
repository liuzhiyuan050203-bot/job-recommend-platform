package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 技能需求月度趋势，对应 spark_tech_trend。
 */
@Data
@TableName("spark_tech_trend")
public class SparkTechTrend {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String batchNo;
    private String statMonth;
    private String tagName;
    private String techDirection;
    private Integer demandCount;
    private BigDecimal avgSalary;
    private BigDecimal momRate;
    private Integer isLatest;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
