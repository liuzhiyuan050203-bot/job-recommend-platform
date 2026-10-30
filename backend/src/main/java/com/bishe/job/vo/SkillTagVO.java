package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class SkillTagVO {

    private Long id;
    private String name;
    private String direction;
    private Integer sortNo;
    private Integer status;
    private LocalDateTime createTime;
}
