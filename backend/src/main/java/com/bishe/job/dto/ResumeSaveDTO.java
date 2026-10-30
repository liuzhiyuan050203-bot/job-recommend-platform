package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class ResumeSaveDTO {

    @NotBlank(message = "简历标题不能为空")
    @Size(max = 128, message = "简历标题长度不能超过 128")
    private String title;

    @Min(value = 0, message = "默认简历取值不正确")
    @Max(value = 1, message = "默认简历取值不正确")
    private Integer isDefault;

    private String educationExp;

    private String projectExp;

    private String internshipExp;

    private String skillDesc;

    private String selfEvaluation;

    @Size(max = 512, message = "附件地址长度不能超过 512")
    private String attachmentUrl;
}
