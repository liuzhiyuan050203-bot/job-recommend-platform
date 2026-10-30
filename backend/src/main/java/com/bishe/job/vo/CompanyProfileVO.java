package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 企业资料 VO
 */
@Data
public class CompanyProfileVO {

    private Long id;
    private Long userId;
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
    /** 0 待审核 1 已通过 2 已驳回 */
    private Integer auditStatus;
    private String auditRemark;
    private LocalDateTime auditTime;
}
