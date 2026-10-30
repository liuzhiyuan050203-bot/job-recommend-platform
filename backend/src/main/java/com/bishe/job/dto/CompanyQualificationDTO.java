package com.bishe.job.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class CompanyQualificationDTO {

    @Size(max = 128, message = "企业全称长度不能超过 128")
    private String companyName;

    @NotBlank(message = "统一社会信用代码不能为空")
    @Size(min = 15, max = 32, message = "统一社会信用代码长度需为 15-32 位")
    private String creditCode;

    @NotBlank(message = "营业执照地址不能为空")
    @Size(max = 512, message = "营业执照地址长度不能超过 512")
    private String licenseUrl;
}
