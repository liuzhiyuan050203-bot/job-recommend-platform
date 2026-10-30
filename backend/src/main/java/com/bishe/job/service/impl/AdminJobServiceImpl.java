package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.dto.AuditDTO;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.JobCategory;
import com.bishe.job.entity.JobPosition;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.JobCategoryMapper;
import com.bishe.job.mapper.JobPositionMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.AdminJobService;
import com.bishe.job.vo.AdminJobVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class AdminJobServiceImpl implements AdminJobService {

    private final JobPositionMapper jobPositionMapper;
    private final EntCompanyMapper entCompanyMapper;
    private final JobCategoryMapper jobCategoryMapper;

    @Override
    public PageResult<AdminJobVO> listJobs(Integer auditStatus, Integer shelfStatus, Long companyId,
                                            String keyword, long current, long size) {
        Page<JobPosition> page = Pages.of(current, size);
        LambdaQueryWrapper<JobPosition> wrapper = new LambdaQueryWrapper<>();

        if (auditStatus != null) {
            wrapper.eq(JobPosition::getAuditStatus, auditStatus);
        }
        if (shelfStatus != null) {
            wrapper.eq(JobPosition::getShelfStatus, shelfStatus);
        }
        if (companyId != null) {
            wrapper.eq(JobPosition::getCompanyId, companyId);
        }
        if (StringUtils.hasText(keyword)) {
            String kw = keyword.trim();
            wrapper.and(w -> w.like(JobPosition::getTitle, kw)
                    .or().like(JobPosition::getTechDirection, kw)
                    .or().like(JobPosition::getCity, kw));
        }

        // 待审核 (0) 优先
        wrapper.orderByAsc(JobPosition::getAuditStatus)
                .orderByDesc(JobPosition::getUpdateTime)
                .orderByDesc(JobPosition::getId);

        jobPositionMapper.selectPage(page, wrapper);
        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, Collections.emptyList());
        }

        List<Long> companyIds = page.getRecords().stream().map(JobPosition::getCompanyId).distinct().toList();
        Map<Long, String> companyNames = entCompanyMapper.selectBatchIds(companyIds).stream()
                .collect(Collectors.toMap(EntCompany::getId, c -> StringUtils.hasText(c.getShortName()) ? c.getShortName() : c.getCompanyName()));

        List<Long> categoryIds = page.getRecords().stream().map(JobPosition::getCategoryId).distinct().toList();
        Map<Long, String> categoryNames = jobCategoryMapper.selectBatchIds(categoryIds).stream()
                .collect(Collectors.toMap(JobCategory::getId, JobCategory::getName));

        List<AdminJobVO> list = page.getRecords().stream().map(job -> {
            AdminJobVO vo = toVO(job);
            vo.setCompanyName(companyNames.get(job.getCompanyId()));
            vo.setCategoryName(categoryNames.get(job.getCategoryId()));
            return vo;
        }).toList();

        return PageResult.of(page, list);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void auditJob(Long id, AuditDTO dto) {
        Long adminId = UserContext.get().getId();
        JobPosition job = jobPositionMapper.selectById(id);
        if (job == null) {
            throw new BusinessException(404, "职位不存在");
        }

        job.setAuditStatus(dto.getAuditStatus());
        job.setAuditRemark(dto.getAuditRemark());
        job.setAuditTime(LocalDateTime.now());
        job.setAuditorId(adminId);

        jobPositionMapper.updateById(job);
    }

    private AdminJobVO toVO(JobPosition job) {
        AdminJobVO vo = new AdminJobVO();
        vo.setId(job.getId());
        vo.setCompanyId(job.getCompanyId());
        vo.setCategoryId(job.getCategoryId());
        vo.setTitle(job.getTitle());
        vo.setTechDirection(job.getTechDirection());
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
        vo.setDescription(job.getDescription());
        vo.setRequirement(job.getRequirement());
        vo.setWelfare(job.getWelfare());
        vo.setShelfStatus(job.getShelfStatus());
        vo.setAuditStatus(job.getAuditStatus());
        vo.setAuditRemark(job.getAuditRemark());
        vo.setAuditTime(job.getAuditTime());
        vo.setAuditorId(job.getAuditorId());
        vo.setPublishTime(job.getPublishTime());
        vo.setViewCount(job.getViewCount());
        vo.setFavoriteCount(job.getFavoriteCount());
        vo.setApplyCount(job.getApplyCount());
        vo.setCreateTime(job.getCreateTime());
        return vo;
    }
}
