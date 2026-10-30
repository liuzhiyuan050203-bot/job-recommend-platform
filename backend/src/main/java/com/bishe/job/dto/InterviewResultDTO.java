package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class InterviewResultDTO {

    @NotNull(message = "面试结果不能为空")
    @Min(value = 0, message = "面试状态取值不正确")
    @Max(value = 3, message = "面试状态取值不正确")
    private Integer interviewStatus;

    @Size(max = 500, message = "备注长度不能超过 500")
    private String remark;
}
