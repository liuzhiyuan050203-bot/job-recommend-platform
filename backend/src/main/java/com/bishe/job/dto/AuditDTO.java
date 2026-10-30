package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class AuditDTO {

    @NotNull(message = "审核结果不能为空")
    @Min(value = 1, message = "审核结果：1通过 2驳回")
    @Max(value = 2, message = "审核结果：1通过 2驳回")
    private Integer auditStatus;

    private String auditRemark;
}
