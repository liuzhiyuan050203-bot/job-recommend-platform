package com.bishe.job.vo;

import lombok.Data;

/**
 * 学生档案摘要。
 */
@Data
public class StudentProfileVO {

    private Long id;
    private String realName;
    private Integer gender;
    private String studentNo;
    private String school;
    private String college;
    private String major;
    private Integer education;
    private String educationName;
    private Integer graduationYear;
    private String expectCity;
    private String expectDirection;
}
