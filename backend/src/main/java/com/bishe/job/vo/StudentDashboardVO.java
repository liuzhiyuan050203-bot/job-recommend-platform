package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 学生求职看板。技能雷达的职位侧是推荐职位（没有推荐时用热门职位）标签上，全体学生的平均熟练度。
 */
@Data
public class StudentDashboardVO {

    private List<StatusCountVO> applicationStatus = new ArrayList<>();
    private SkillRadarVO skillRadar = new SkillRadarVO();
    private ProfileBriefVO profile = new ProfileBriefVO();
    private List<RecommendBriefVO> recommendTop = new ArrayList<>();

    @Data
    public static class StatusCountVO {
        private Integer status;
        private String label;
        private long count;
    }

    @Data
    public static class SkillRadarVO {
        private List<String> skills = new ArrayList<>();
        private List<Integer> myLevels = new ArrayList<>();
        private List<BigDecimal> jobAvgLevels = new ArrayList<>();
    }

    @Data
    public static class ProfileBriefVO {
        private String city;
        private String techDirection;
        private Integer education;
        private BigDecimal experienceYears;
        private List<String> skills = new ArrayList<>();
    }

    @Data
    public static class RecommendBriefVO {
        private Long positionId;
        private String title;
        private String companyName;
        private String city;
        private String techDirection;
        private Integer salaryMin;
        private Integer salaryMax;
        private BigDecimal matchScore;
        private String reason;
    }
}
