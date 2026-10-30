package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class UserStatusDTO {

    @NotNull(message = "状态不能为空")
    @Min(value = 1, message = "状态：1启用 2禁用")
    @Max(value = 2, message = "状态：1启用 2禁用")
    private Integer status;
}
