package com.bishe.job.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class FavoriteCreateDTO {

    @NotNull(message = "职位不能为空")
    private Long jobId;
}
