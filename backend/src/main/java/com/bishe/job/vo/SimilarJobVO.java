package com.bishe.job.vo;

import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;

import java.util.ArrayList;
import java.util.List;

/**
 * 相似职位。similarity 为 0 到 100，当前列表内最高分为 100。
 */
@Data
public class SimilarJobVO {

    private Long id;
    private String title;
    private String companyName;
    private String city;
    private String province;
    private String techDirection;
    private Integer salaryMin;
    private Integer salaryMax;
    private Integer salaryMonths;
    private Integer education;
    private List<String> tagNames = new ArrayList<>();
    private Double similarity;

    @JsonIgnore
    private Double rawScore;
}
