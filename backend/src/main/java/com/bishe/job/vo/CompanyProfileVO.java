package com.bishe.job.vo;

import lombok.Data;

/**
 * 企业资料摘要。
 */
@Data
public class CompanyProfileVO {

    private Long id;
    private String companyName;
    private String shortName;
    private String industry;
    private Integer scale;
    private String province;
    private String city;
    private String address;
    private String creditCode;
    private String contactName;
    private String contactPhone;
    private String contactEmail;
    /** 0 待审核 1 已通过 2 已驳回 */
    private Integer auditStatus;
    private String auditRemark;
}
