package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.time.LocalDate;

@Data
public class StudentProfileUpdateDTO {

    @NotBlank(message = "真实姓名不能为空")
    @Size(max = 64, message = "真实姓名长度不能超过 64")
    private String realName;

    @NotNull(message = "性别不能为空")
    @Min(value = 0, message = "性别取值不合法")
    @Max(value = 2, message = "性别取值不合法")
    private Integer gender;

    private LocalDate birthday;

    @Size(max = 32, message = "学号长度不能超过 32")
    private String studentNo;

    @Size(max = 128, message = "学校长度不能超过 128")
    private String school;

    @Size(max = 128, message = "学院长度不能超过 128")
    private String college;

    @Size(max = 128, message = "专业长度不能超过 128")
    private String major;

    @NotNull(message = "学历不能为空")
    @Min(value = 1, message = "学历代码 1-4")
    @Max(value = 4, message = "学历代码 1-4")
    private Integer education;

    @NotNull(message = "毕业年份不能为空")
    private Integer graduationYear;

    @Size(max = 64, message = "期望城市长度不能超过 64")
    private String expectCity;

    private Integer expectSalaryMin;

    private Integer expectSalaryMax;

    @Size(max = 64, message = "期望方向长度不能超过 64")
    private String expectDirection;

    @Size(max = 1000, message = "自我介绍长度不能超过 1000")
    private String selfIntro;
}
