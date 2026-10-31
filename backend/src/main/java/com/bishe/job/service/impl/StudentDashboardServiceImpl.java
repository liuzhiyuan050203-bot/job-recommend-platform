package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bishe.job.common.PageResult;
import com.bishe.job.entity.JobApplication;
import com.bishe.job.entity.StuProfile;
import com.bishe.job.mapper.JobApplicationMapper;
import com.bishe.job.mapper.StatsQueryMapper;
import com.bishe.job.mapper.StuProfileMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.ApplicationStateMachine;
import com.bishe.job.service.RecommendService;
import com.bishe.job.service.StudentDashboardService;
import com.bishe.job.service.StudentProfileService;
import com.bishe.job.vo.DashboardAggVO;
import com.bishe.job.vo.RecommendJobVO;
import com.bishe.job.vo.SkillVO;
import com.bishe.job.vo.StudentDashboardVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class StudentDashboardServiceImpl implements StudentDashboardService {

    private static final int RADAR_LIMIT = 8;
    private static final int RECOMMEND_LIMIT = 5;

    private final JobApplicationMapper jobApplicationMapper;
    private final StuProfileMapper stuProfileMapper;
    private final StatsQueryMapper statsQueryMapper;
    private final StudentProfileService studentProfileService;
    private final RecommendService recommendService;

    @Override
    public StudentDashboardVO dashboard() {
        Long userId = UserContext.require().getId();
        StudentDashboardVO vo = new StudentDashboardVO();
        vo.setApplicationStatus(statusCounts(userId));
        List<SkillVO> skills = studentProfileService.listSkills();
        vo.setProfile(profileOf(userId, skills));
        List<RecommendJobVO> recommended = loadRecommend();
        vo.setRecommendTop(slim(recommended));
        vo.setSkillRadar(radar(recommended, skills));
        return vo;
    }

    private List<StudentDashboardVO.StatusCountVO> statusCounts(Long userId) {
        List<StudentDashboardVO.StatusCountVO> counts = new ArrayList<>();
        for (int status = 0; status <= 4; status++) {
            Long total = jobApplicationMapper.selectCount(new LambdaQueryWrapper<JobApplication>()
                    .eq(JobApplication::getUserId, userId)
                    .eq(JobApplication::getStatus, status));
            StudentDashboardVO.StatusCountVO item = new StudentDashboardVO.StatusCountVO();
            item.setStatus(status);
            item.setLabel(ApplicationStateMachine.nameOf(status));
            item.setCount(total == null ? 0L : total);
            counts.add(item);
        }
        return counts;
    }

    private StudentDashboardVO.ProfileBriefVO profileOf(Long userId, List<SkillVO> skills) {
        StudentDashboardVO.ProfileBriefVO brief = new StudentDashboardVO.ProfileBriefVO();
        StuProfile profile = stuProfileMapper.selectOne(new LambdaQueryWrapper<StuProfile>()
                .eq(StuProfile::getUserId, userId));
        if (profile != null) {
            brief.setCity(blankToNull(profile.getExpectCity()));
            brief.setTechDirection(blankToNull(profile.getExpectDirection()));
            brief.setEducation(profile.getEducation());
            brief.setExperienceYears(experienceYears(profile.getGraduationYear()));
        } else {
            brief.setExperienceYears(BigDecimal.ZERO.setScale(1, RoundingMode.HALF_UP));
        }
        List<String> names = new ArrayList<>();
        for (SkillVO skill : skills) {
            if (StringUtils.hasText(skill.getTagName())) {
                names.add(skill.getTagName().trim());
            }
        }
        brief.setSkills(names);
        return brief;
    }

    /**
     * 档案没有工作年限字段。未毕业按应届 0 年，已毕业按距毕业年份的整年，供薪资预测使用。
     */
    private BigDecimal experienceYears(Integer graduationYear) {
        int current = LocalDate.now().getYear();
        if (graduationYear == null || graduationYear >= current) {
            return BigDecimal.ZERO.setScale(1, RoundingMode.HALF_UP);
        }
        int years = Math.min(40, current - graduationYear);
        return BigDecimal.valueOf(years).setScale(1, RoundingMode.HALF_UP);
    }

    private List<RecommendJobVO> loadRecommend() {
        try {
            PageResult<RecommendJobVO> page = recommendService.pageForCurrentStudent(1, RECOMMEND_LIMIT);
            if (page == null || page.getRecords() == null) {
                return List.of();
            }
            return page.getRecords();
        } catch (Exception ex) {
            log.warn("学生看板读取推荐失败: {}", ex.getMessage());
            return List.of();
        }
    }

    private List<StudentDashboardVO.RecommendBriefVO> slim(List<RecommendJobVO> jobs) {
        List<StudentDashboardVO.RecommendBriefVO> list = new ArrayList<>();
        int limit = Math.min(RECOMMEND_LIMIT, jobs.size());
        for (int i = 0; i < limit; i++) {
            RecommendJobVO job = jobs.get(i);
            StudentDashboardVO.RecommendBriefVO item = new StudentDashboardVO.RecommendBriefVO();
            item.setPositionId(job.getPositionId());
            item.setTitle(job.getTitle());
            item.setCompanyName(job.getCompanyName());
            item.setCity(job.getCity());
            item.setTechDirection(job.getTechDirection());
            item.setSalaryMin(job.getSalaryMin());
            item.setSalaryMax(job.getSalaryMax());
            item.setMatchScore(job.getMatchScore());
            item.setReason(job.getReason());
            list.add(item);
        }
        return list;
    }

    /**
     * 坐标轴优先取推荐职位技能；没有推荐标签时改用在架热门职位标签。
     * 职位表没有要求熟练度，jobAvgLevels 用全体学生在该标签上的平均熟练度。
     */
    private StudentDashboardVO.SkillRadarVO radar(List<RecommendJobVO> jobs, List<SkillVO> mine) {
        LinkedHashSet<String> axes = new LinkedHashSet<>();
        for (RecommendJobVO job : jobs) {
            if (job.getTagNames() == null) {
                continue;
            }
            for (String name : job.getTagNames()) {
                if (StringUtils.hasText(name)) {
                    axes.add(name.trim());
                }
            }
        }
        if (axes.isEmpty()) {
            List<DashboardAggVO> hot = statsQueryMapper.hotJobTags();
            if (hot != null) {
                for (DashboardAggVO row : hot) {
                    if (row != null && StringUtils.hasText(row.getLabel())) {
                        axes.add(row.getLabel().trim());
                    }
                }
            }
        }
        List<String> skills = new ArrayList<>();
        for (String name : axes) {
            if (skills.size() >= RADAR_LIMIT) {
                break;
            }
            skills.add(name);
        }
        if (skills.size() < RADAR_LIMIT) {
            for (SkillVO skill : mine) {
                if (skills.size() >= RADAR_LIMIT) {
                    break;
                }
                if (!StringUtils.hasText(skill.getTagName())) {
                    continue;
                }
                String name = skill.getTagName().trim();
                if (!skills.contains(name)) {
                    skills.add(name);
                }
            }
        }
        Map<String, Integer> mineLevel = new LinkedHashMap<>();
        for (SkillVO skill : mine) {
            if (!StringUtils.hasText(skill.getTagName())) {
                continue;
            }
            mineLevel.put(skill.getTagName().trim(), skill.getProficiency() == null ? 0 : skill.getProficiency());
        }
        Map<String, BigDecimal> market = new LinkedHashMap<>();
        List<DashboardAggVO> averages = statsQueryMapper.skillAvgLevels();
        if (averages != null) {
            for (DashboardAggVO row : averages) {
                if (row == null || !StringUtils.hasText(row.getLabel())) {
                    continue;
                }
                market.put(row.getLabel().trim(), clampLevel(row.getAvgLevel()));
            }
        }
        StudentDashboardVO.SkillRadarVO radar = new StudentDashboardVO.SkillRadarVO();
        radar.setSkills(skills);
        for (String name : skills) {
            int level = mineLevel.getOrDefault(name, 0);
            if (level < 0) {
                level = 0;
            } else if (level > 5) {
                level = 5;
            }
            radar.getMyLevels().add(level);
            radar.getJobAvgLevels().add(market.getOrDefault(name, BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP)));
        }
        return radar;
    }

    private BigDecimal clampLevel(BigDecimal value) {
        if (value == null) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        BigDecimal scaled = value.setScale(2, RoundingMode.HALF_UP);
        if (scaled.compareTo(BigDecimal.ZERO) < 0) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        if (scaled.compareTo(new BigDecimal("5")) > 0) {
            return new BigDecimal("5.00");
        }
        return scaled;
    }

    private String blankToNull(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        return value.trim();
    }
}
