package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.JobApplication;
import com.bishe.job.entity.JobPosition;
import com.bishe.job.mapper.JobApplicationMapper;
import com.bishe.job.mapper.JobPositionMapper;
import com.bishe.job.mapper.StatsQueryMapper;
import com.bishe.job.service.ApplicationStateMachine;
import com.bishe.job.service.CompanyDashboardService;
import com.bishe.job.service.CompanySupport;
import com.bishe.job.vo.CompanyDashboardVO;
import com.bishe.job.vo.DashboardAggVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
public class CompanyDashboardServiceImpl implements CompanyDashboardService {

    private final CompanySupport companySupport;
    private final JobPositionMapper jobPositionMapper;
    private final JobApplicationMapper jobApplicationMapper;
    private final StatsQueryMapper statsQueryMapper;

    @Override
    public CompanyDashboardVO dashboard() {
        EntCompany company = companySupport.requireCurrent();
        CompanyDashboardVO vo = new CompanyDashboardVO();
        vo.setJobs(jobsOf(company.getId()));
        vo.setApplicationStatus(statusCounts(company.getId()));
        vo.setApplicantSkills(skillsOf(company.getId()));
        return vo;
    }

    private List<CompanyDashboardVO.JobItemVO> jobsOf(Long companyId) {
        List<JobPosition> rows = jobPositionMapper.selectList(new LambdaQueryWrapper<JobPosition>()
                .eq(JobPosition::getCompanyId, companyId)
                .orderByDesc(JobPosition::getApplyCount)
                .orderByDesc(JobPosition::getId));
        List<CompanyDashboardVO.JobItemVO> jobs = new ArrayList<>();
        for (JobPosition row : rows) {
            CompanyDashboardVO.JobItemVO item = new CompanyDashboardVO.JobItemVO();
            item.setPositionId(row.getId());
            item.setTitle(row.getTitle());
            item.setViewCount(nvl(row.getViewCount()));
            item.setFavoriteCount(nvl(row.getFavoriteCount()));
            item.setApplyCount(nvl(row.getApplyCount()));
            item.setShelfStatus(row.getShelfStatus());
            jobs.add(item);
        }
        return jobs;
    }

    private List<CompanyDashboardVO.StatusCountVO> statusCounts(Long companyId) {
        List<CompanyDashboardVO.StatusCountVO> counts = new ArrayList<>();
        for (int status = 0; status <= 4; status++) {
            Long total = jobApplicationMapper.selectCount(new LambdaQueryWrapper<JobApplication>()
                    .eq(JobApplication::getCompanyId, companyId)
                    .eq(JobApplication::getStatus, status));
            CompanyDashboardVO.StatusCountVO item = new CompanyDashboardVO.StatusCountVO();
            item.setStatus(status);
            item.setLabel(ApplicationStateMachine.nameOf(status));
            item.setCount(total == null ? 0L : total);
            counts.add(item);
        }
        return counts;
    }

    private List<CompanyDashboardVO.SkillCountVO> skillsOf(Long companyId) {
        List<DashboardAggVO> rows = statsQueryMapper.applicantSkillCounts(companyId);
        List<CompanyDashboardVO.SkillCountVO> skills = new ArrayList<>();
        if (rows == null) {
            return skills;
        }
        for (DashboardAggVO row : rows) {
            if (row == null || row.getLabel() == null || row.getLabel().isBlank()) {
                continue;
            }
            CompanyDashboardVO.SkillCountVO item = new CompanyDashboardVO.SkillCountVO();
            item.setName(row.getLabel().trim());
            item.setCount(row.getTotal() == null ? 0L : row.getTotal());
            skills.add(item);
        }
        return skills;
    }

    private int nvl(Integer value) {
        return value == null ? 0 : value;
    }
}
