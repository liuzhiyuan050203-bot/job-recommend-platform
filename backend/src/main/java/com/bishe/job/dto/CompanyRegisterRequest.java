package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class CompanyRegisterRequest {

    @NotBlank(message = "用户名不能为空")
    @Size(min = 3, max = 64, message = "用户名长度需为 3-64 位")
    @Pattern(regexp = "^[A-Za-z][A-Za-z0-9_]{2,63}$", message = "用户名需以字母开头，仅含字母、数字或下划线")
    private String username;

    @NotBlank(message = "密码不能为空")
    @Size(min = 6, max = 32, message = "密码长度需为 6-32 位")
    private String password;

    @Size(max = 64, message = "昵称长度不能超过 64")
    private String nickname;

    @NotBlank(message = "企业全称不能为空")
    @Size(max = 128, message = "企业全称长度不能超过 128")
    private String companyName;

    @Size(max = 64, message = "企业简称长度不能超过 64")
    private String shortName;

    @NotBlank(message = "统一社会信用代码不能为空")
    @Size(min = 18, max = 18, message = "统一社会信用代码须为 18 位")
    @Pattern(regexp = "^[0-9A-Za-z]+$", message = "统一社会信用代码仅能包含字母和数字")
    private String creditCode;

    @NotBlank(message = "联系人不能为空")
    @Size(max = 64, message = "联系人长度不能超过 64")
    private String contactName;

    @Size(max = 20, message = "联系电话长度不能超过 20")
    private String contactPhone;

    @Size(max = 128, message = "联系邮箱长度不能超过 128")
    private String contactEmail;

    @Size(max = 64, message = "行业长度不能超过 64")
    private String industry;

    @Min(value = 0, message = "企业规模取值不正确")
    @Max(value = 6, message = "企业规模取值不正确")
    private Integer scale;

    @Size(max = 32, message = "省份长度不能超过 32")
    private String province;

    @Size(max = 32, message = "城市长度不能超过 32")
    private String city;

    @Size(max = 255, message = "地址长度不能超过 255")
    private String address;
}
