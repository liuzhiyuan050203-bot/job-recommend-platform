package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDate;

/**
 * 学生档案 VO
 */
@Data
public class StudentProfileVO {

    private Long id;
    private Long userId;
    private String realName;
    private Integer gender;
    private String genderName;
    private LocalDate birthday;
    private String studentNo;
    private String school;
    private String college;
    private String major;
    private Integer education;
    private String educationName;
    private Integer graduationYear;
    private String expectCity;
    private Integer expectSalaryMin;
    private Integer expectSalaryMax;
    private String expectDirection;
    private String selfIntro;
}
