package com.bishe.job.security;

import lombok.Data;

/**
 * 当前请求的登录用户，放在 ThreadLocal 中，请求结束必须清理。
 */
@Data
public class LoginUser {

    private Long id;
    private String username;
    private Integer role;
    private Integer status;
    private String nickname;
    /**
     * 企业资质审核状态。非企业账号为空。
     */
    private Integer companyAuditStatus;
}
