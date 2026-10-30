package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class SkillTagDTO {

    @NotBlank(message = "技能名称不能为空")
    @Size(max = 64, message = "技能名称长度不能超过 64")
    private String name;

    @NotBlank(message = "所属技术方向不能为空")
    @Size(max = 64, message = "技术方向长度不能超过 64")
    private String direction;

    private Integer sortNo;

    @Min(value = 0, message = "状态取值不合法")
    @Max(value = 1, message = "状态取值不合法")
    private Integer status;
}
