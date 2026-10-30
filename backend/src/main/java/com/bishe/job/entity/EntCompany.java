package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 企业资料与资质，对应 ent_company。
 */
@Data
@TableName("ent_company")
public class EntCompany {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;
    private String companyName;
    private String shortName;
    private String logoUrl;
    private String industry;
    /** 0 未知到 6 一万人以上 */
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
    private Long auditorId;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
