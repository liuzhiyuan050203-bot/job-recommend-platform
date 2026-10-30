package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.time.LocalDate;

@Data
public class StudentProfileUpdateDTO {

    @NotBlank(message = "真实姓名不能为空")
    private String realName;

    @NotNull(message = "性别不能为空")
    @Min(value = 0, message = "性别取值不合法")
    @Max(value = 2, message = "性别取值不合法")
    private Integer gender;

    private LocalDate birthday;

    private String studentNo;

    private String school;

    private String college;

    private String major;

    @NotNull(message = "学历不能为空")
    @Min(value = 1, message = "学历代码 1-4")
    @Max(value = 4, message = "学历代码 1-4")
    private Integer education;

    @NotNull(message = "毕业年份不能为空")
    private Integer graduationYear;

    private String expectCity;

    private Integer expectSalaryMin;

    private Integer expectSalaryMax;

    private String expectDirection;

    private String selfIntro;
}
