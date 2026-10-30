package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class AdminCompanyVO {

    private Long id;
    private Long userId;
    private String username;
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
    private String creditCode;
    private String licenseUrl;
    private String contactName;
    private String contactPhone;
    private String contactEmail;
    private Integer auditStatus;
    private String auditRemark;
    private LocalDateTime auditTime;
    private Long auditorId;
    private LocalDateTime createTime;
}
