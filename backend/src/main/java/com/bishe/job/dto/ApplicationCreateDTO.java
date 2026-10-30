package com.bishe.job.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class ApplicationCreateDTO {

    @NotNull(message = "职位不能为空")
    private Long jobId;

    @NotNull(message = "请选择简历")
    private Long resumeId;
}
