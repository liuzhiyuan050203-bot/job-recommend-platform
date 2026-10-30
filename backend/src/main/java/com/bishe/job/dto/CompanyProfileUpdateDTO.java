package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class CompanyProfileUpdateDTO {

    @Size(max = 128, message = "企业全称长度不能超过 128")
    private String companyName;

    @Size(max = 64, message = "企业简称长度不能超过 64")
    private String shortName;

    @Size(max = 512, message = "徽标地址长度不能超过 512")
    private String logoUrl;

    @Size(max = 64, message = "行业长度不能超过 64")
    private String industry;

    @Min(value = 0, message = "人员规模取值不合法")
    @Max(value = 6, message = "人员规模取值不合法")
    private Integer scale;

    @Size(max = 32, message = "省份长度不能超过 32")
    private String province;

    @Size(max = 32, message = "城市长度不能超过 32")
    private String city;

    @Size(max = 255, message = "地址长度不能超过 255")
    private String address;

    @Size(max = 255, message = "网站长度不能超过 255")
    private String website;

    @Size(max = 65535, message = "企业简介过长")
    private String intro;

    @Size(max = 64, message = "联系人长度不能超过 64")
    private String contactName;

    @Size(max = 20, message = "联系电话长度不能超过 20")
    private String contactPhone;

    @Size(max = 128, message = "联系邮箱长度不能超过 128")
    private String contactEmail;
}
