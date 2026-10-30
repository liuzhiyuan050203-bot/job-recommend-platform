package com.bishe.job.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class CompanyQualificationDTO {

    private String companyName;

    @NotBlank(message = "统一社会信用代码不能为空")
    private String creditCode;

    @NotBlank(message = "营业执照地址不能为空")
    private String licenseUrl;
}
