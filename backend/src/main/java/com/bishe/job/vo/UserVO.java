package com.bishe.job.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 对外用户信息。roleName 为 student / company / admin。
 */
@Data
public class UserVO {

    private Long id;
    private String username;
    private Integer role;
    private String roleName;
    private String nickname;
    private String phone;
    private String email;
    private String avatar;
    private Integer status;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime lastLoginTime;

    /**
     * 企业资质审核状态。学生和管理员为空。
     */
    private Integer companyAuditStatus;

    private StudentProfileVO profile;
    private CompanyProfileVO company;
}
