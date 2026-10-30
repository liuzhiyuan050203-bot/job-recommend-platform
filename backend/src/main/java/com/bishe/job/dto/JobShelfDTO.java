package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class JobShelfDTO {

    @NotNull(message = "上下架状态不能为空")
    @Min(value = 0, message = "上下架状态取值不正确")
    @Max(value = 1, message = "上下架状态取值不正确")
    private Integer shelfStatus;
}
