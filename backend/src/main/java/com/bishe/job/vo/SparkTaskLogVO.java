package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class SparkTaskLogVO {

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
}
