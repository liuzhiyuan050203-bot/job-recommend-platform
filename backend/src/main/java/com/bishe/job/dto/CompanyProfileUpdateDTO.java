package com.bishe.job.dto;

import lombok.Data;

@Data
public class CompanyProfileUpdateDTO {

    private String companyName;
    private String shortName;
    private String logoUrl;
    private String industry;
    private Integer scale;
    private String province;
    private String city;
    private String address;
    private String website;
    private String intro;
    private String contactName;
    private String contactPhone;
    private String contactEmail;
}
