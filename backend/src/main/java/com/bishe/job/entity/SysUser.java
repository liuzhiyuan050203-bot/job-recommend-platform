package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 统一登录账号，对应 sys_user。
 */
@Data
@TableName("sys_user")
public class SysUser {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String username;

    /**
     * BCrypt 哈希。@JsonIgnore 只作用于 Jackson 序列化，避免接口带回密码；
     * MyBatis 仍通过 getter/setter 读写该列。
     */
    @JsonIgnore
    private String password;

    /** 1 学生 2 企业 3 管理员 */
    private Integer role;

    private String nickname;
    private String phone;
    private String email;
    private String avatar;

    /** 0 待审核 1 正常 2 禁用 3 已驳回 */
    private Integer status;

    private String auditRemark;
    private LocalDateTime auditTime;
    private Long auditorId;
    private LocalDateTime lastLoginTime;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
