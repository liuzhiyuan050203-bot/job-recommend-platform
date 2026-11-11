package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.JobFavorite;
import com.bishe.job.entity.JobPosition;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.JobFavoriteMapper;
import com.bishe.job.mapper.JobPositionMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.BehaviorLogService;
import com.bishe.job.service.PositionTags;
import com.bishe.job.service.StudentFavoriteService;
import com.bishe.job.service.VisibleJobSupport;
import com.bishe.job.vo.PositionTagVO;
import com.bishe.job.vo.PublicJobVO;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class StudentFavoriteServiceImpl implements StudentFavoriteService {

    private final JobFavoriteMapper jobFavoriteMapper;
    private final JobPositionMapper jobPositionMapper;
    private final EntCompanyMapper entCompanyMapper;
    private final VisibleJobSupport visibleJobSupport;
    private final BehaviorLogService behaviorLogService;
    private final PositionTags positionTags;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void add(Long jobId) {
        Long userId = UserContext.require().getId();
        visibleJobSupport.require(jobId);
        JobFavorite existing = jobFavoriteMapper.selectAny(userId, jobId);
        if (existing != null && Integer.valueOf(0).equals(existing.getDeleted())) {
            return;
        }
        boolean created;
        if (existing != null) {
            jobFavoriteMapper.restore(existing.getId());
            created = true;
        } else {
            try {
                JobFavorite row = new JobFavorite();
                row.setUserId(userId);
                row.setPositionId(jobId);
                row.setDeleted(0);
                jobFavoriteMapper.insert(row);
                created = true;
            } catch (DuplicateKeyException ex) {
                created = false;
            }
        }
        if (created) {
            jobPositionMapper.incrFavorite(jobId);
            behaviorLogService.logJob(BehaviorLogService.FAVORITE, jobId);
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void remove(Long jobId) {
        Long userId = UserContext.require().getId();
        JobFavorite existing = jobFavoriteMapper.selectAny(userId, jobId);
        if (existing == null || !Integer.valueOf(0).equals(existing.getDeleted())) {
            return;
        }
        jobFavoriteMapper.deleteById(existing.getId());
        jobPositionMapper.decrFavorite(jobId);
    }

    @Override
    public PageResult<PublicJobVO> page(long current, long size) {
        Long userId = UserContext.require().getId();
        Page<JobFavorite> page = Pages.of(current, size);
        jobFavoriteMapper.selectPage(page, new LambdaQueryWrapper<JobFavorite>()
                .eq(JobFavorite::getUserId, userId)
                .orderByDesc(JobFavorite::getUpdateTime)
                .orderByDesc(JobFavorite::getId));
        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, List.of());
        }
        List<Long> jobIds = page.getRecords().stream().map(JobFavorite::getPositionId).distinct().toList();
        Map<Long, JobPosition> jobs = jobPositionMapper.selectBatchIds(jobIds).stream()
                .collect(Collectors.toMap(JobPosition::getId, job -> job));
        List<Long> companyIds = jobs.values().stream().map(JobPosition::getCompanyId).distinct().toList();
        Map<Long, EntCompany> companies = companyIds.isEmpty() ? Map.of()
                : entCompanyMapper.selectBatchIds(companyIds).stream()
                .collect(Collectors.toMap(EntCompany::getId, company -> company));
        Map<Long, List<PositionTagVO>> tags = positionTags.of(jobIds);
        List<PublicJobVO> records = new ArrayList<>();
        for (JobFavorite favorite : page.getRecords()) {
            records.add(toCard(favorite.getPositionId(), jobs.get(favorite.getPositionId()), companies, tags));
        }
        return PageResult.of(page, records);
    }

    private PublicJobVO toCard(Long jobId, JobPosition job, Map<Long, EntCompany> companies,
                               Map<Long, List<PositionTagVO>> tags) {
        PublicJobVO vo = new PublicJobVO();
        vo.setId(jobId);
        vo.setFavorited(true);
        if (job == null) {
            vo.setTitle("职位已删除");
            return vo;
        }
        EntCompany company = companies.get(job.getCompanyId());
        vo.setTitle(job.getTitle());
        vo.setSourceCode(job.getDataSource());
        vo.setSalaryEstimated(PublicJobServiceImpl.isEstimatedSource(job.getDataSource()));
        vo.setTechDirection(job.getTechDirection());
        vo.setCategoryId(job.getCategoryId());
        vo.setProvince(job.getProvince());
        vo.setCity(job.getCity());
        vo.setDistrict(job.getDistrict());
        vo.setSalaryMin(job.getSalaryMin());
        vo.setSalaryMax(job.getSalaryMax());
        vo.setSalaryMonths(job.getSalaryMonths());
        vo.setEducation(job.getEducation());
        vo.setExperienceReq(job.getExperienceReq());
        vo.setJobType(job.getJobType());
        vo.setHeadcount(job.getHeadcount());
        vo.setCompanyId(job.getCompanyId());
        vo.setShelfStatus(job.getShelfStatus());
        vo.setAuditStatus(job.getAuditStatus());
        if (company != null) {
            vo.setCompanyName(StringUtils.hasText(company.getShortName()) ? company.getShortName() : company.getCompanyName());
            vo.setCompanyLogo(company.getLogoUrl());
        }
        vo.setPublishTime(job.getPublishTime());
        vo.setViewCount(job.getViewCount());
        vo.setFavoriteCount(job.getFavoriteCount());
        vo.setApplyCount(job.getApplyCount());
        List<PositionTagVO> tagList = tags.getOrDefault(jobId, List.of());
        vo.setTagIds(tagList.stream().map(PositionTagVO::getTagId).toList());
        vo.setTagNames(tagList.stream().map(PositionTagVO::getTagName).toList());
        return vo;
    }
}
