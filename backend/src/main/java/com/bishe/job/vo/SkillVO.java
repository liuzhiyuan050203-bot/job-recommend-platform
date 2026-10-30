package com.bishe.job.vo;

import lombok.Data;

@Data
public class SkillVO {

    private Long id;
    private Long tagId;
    private String tagName;
    private String direction;
    private Integer proficiency;
}
