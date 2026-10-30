package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class AdminUserVO {

    private Long id;
    private String username;
    private Integer role;
    private String roleName;
    private String nickname;
    private String phone;
    private String email;
    private String avatar;
    private Integer status;
    private String auditRemark;
    private LocalDateTime lastLoginTime;
    private LocalDateTime createTime;
}
