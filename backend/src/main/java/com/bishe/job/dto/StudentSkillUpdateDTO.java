package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class StudentSkillUpdateDTO {

    @NotNull(message = "熟练度不能为空")
    @Min(value = 1, message = "熟练度范围为 1-5")
    @Max(value = 5, message = "熟练度范围为 1-5")
    private Integer proficiency;
}
