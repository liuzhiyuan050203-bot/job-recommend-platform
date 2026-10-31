package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class AiSessionVO {

    private Long id;
    private String title;
    private Integer agentType;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
