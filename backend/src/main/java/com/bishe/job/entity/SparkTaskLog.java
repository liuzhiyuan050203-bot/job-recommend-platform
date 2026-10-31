package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * Spark 任务日志，对应 spark_task_log。
 */
@Data
@TableName("spark_task_log")
public class SparkTaskLog {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String batchNo;
    private String taskCode;
    private String taskName;
    private Integer status;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private Long inputCount;
    private Long outputCount;
    private String resultMsg;
    private String errorMsg;
    private String paramsJson;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
