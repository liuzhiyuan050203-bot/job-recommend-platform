package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class StudentRegisterRequest {

    @NotBlank(message = "用户名不能为空")
    @Size(min = 3, max = 64, message = "用户名长度需为 3-64 位")
    @Pattern(regexp = "^[A-Za-z][A-Za-z0-9_]{2,63}$", message = "用户名需以字母开头，仅含字母、数字或下划线")
    private String username;

    @NotBlank(message = "密码不能为空")
    @Size(min = 6, max = 32, message = "密码长度需为 6-32 位")
    private String password;

    @NotBlank(message = "昵称不能为空")
    @Size(max = 64, message = "昵称长度不能超过 64")
    private String nickname;

    @NotBlank(message = "真实姓名不能为空")
    @Size(max = 64, message = "真实姓名长度不能超过 64")
    private String realName;

    @Min(value = 0, message = "性别取值不正确")
    @Max(value = 2, message = "性别取值不正确")
    private Integer gender;

    @NotNull(message = "请选择学历")
    @Min(value = 1, message = "学历取值不正确")
    @Max(value = 4, message = "学历取值不正确")
    private Integer education;

    @NotNull(message = "请填写毕业年份")
    @Min(value = 2000, message = "毕业年份不正确")
    @Max(value = 2100, message = "毕业年份不正确")
    private Integer graduationYear;

    @Size(max = 20, message = "手机号长度不能超过 20")
    private String phone;

    @Size(max = 128, message = "邮箱长度不能超过 128")
    private String email;

    @Size(max = 32, message = "学号长度不能超过 32")
    private String studentNo;

    @Size(max = 128, message = "学校长度不能超过 128")
    private String school;

    @Size(max = 128, message = "学院长度不能超过 128")
    private String college;

    @Size(max = 128, message = "专业长度不能超过 128")
    private String major;

    @Size(max = 64, message = "期望城市长度不能超过 64")
    private String expectCity;

    @Size(max = 64, message = "期望方向长度不能超过 64")
    private String expectDirection;
}
