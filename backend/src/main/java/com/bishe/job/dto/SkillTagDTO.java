package com.bishe.job.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class SkillTagDTO {

    @NotBlank(message = "技能名称不能为空")
    private String name;

    @NotBlank(message = "所属技术方向不能为空")
    private String direction;

    private Integer sortNo;

    private Integer status;
}
