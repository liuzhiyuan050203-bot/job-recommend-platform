package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 省级就业分布，对应 spark_region_dist。
 */
@Data
@TableName("spark_region_dist")
public class SparkRegionDist {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String batchNo;
    private String provinceName;
    private String adcode;
    private Integer jobCount;
    private Integer companyCount;
    private BigDecimal avgSalary;
    private Integer applyCount;
    private Integer isLatest;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
