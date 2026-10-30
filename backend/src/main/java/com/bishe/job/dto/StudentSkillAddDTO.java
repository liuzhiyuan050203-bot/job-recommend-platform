package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class StudentSkillAddDTO {

    /** 技能标签编号（与 tagName 二选一） */
    private Long skillTagId;

    /** 技能名称（若未传 skillTagId 则按名称匹配或自动创建） */
    @Size(max = 64, message = "技能名称长度不能超过 64")
    private String tagName;

    /** 技术方向（可选，未传时取默认方向） */
    @Size(max = 64, message = "技术方向长度不能超过 64")
    private String direction;

    @NotNull(message = "熟练度不能为空")
    @Min(value = 1, message = "熟练度范围为 1-5")
    @Max(value = 5, message = "熟练度范围为 1-5")
    private Integer proficiency;
}
