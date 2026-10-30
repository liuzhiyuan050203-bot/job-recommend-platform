package com.bishe.job.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ApplicationLogVO {

    private Long id;
    private Long applicationId;
    private Integer fromStatus;
    private String fromStatusName;
    private Integer toStatus;
    private String toStatusName;
    private Long operatorId;
    private String operatorName;
    private String remark;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;
}
