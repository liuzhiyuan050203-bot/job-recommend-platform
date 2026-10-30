package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class AuditDTO {

    @NotNull(message = "审核结果不能为空")
    @Min(value = 1, message = "审核结果：1通过 2驳回")
    @Max(value = 2, message = "审核结果：1通过 2驳回")
    private Integer auditStatus;

    @Size(max = 255, message = "审核意见长度不能超过 255")
    private String auditRemark;
}
