package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.dto.JobSaveDTO;
import com.bishe.job.dto.JobShelfDTO;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.JobCategory;
import com.bishe.job.entity.JobPosition;
import com.bishe.job.entity.JobPositionTag;
import com.bishe.job.entity.SkillTag;
import com.bishe.job.mapper.JobCategoryMapper;
import com.bishe.job.mapper.JobPositionMapper;
import com.bishe.job.mapper.JobPositionTagMapper;
import com.bishe.job.mapper.SkillTagMapper;
import com.bishe.job.service.CompanyJobService;
import com.bishe.job.service.CompanySupport;
import com.bishe.job.service.PositionTags;
import com.bishe.job.vo.CompanyJobVO;
import com.bishe.job.vo.PositionTagVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class CompanyJobServiceImpl implements CompanyJobService {

    private final CompanySupport companySupport;
    private final JobPositionMapper jobPositionMapper;
    private final JobPositionTagMapper jobPositionTagMapper;
    private final JobCategoryMapper jobCategoryMapper;
    private final SkillTagMapper skillTagMapper;
    private final PositionTags positionTags;

    @Override
    public PageResult<CompanyJobVO> page(long current, long size) {
        EntCompany company = companySupport.requireCurrent();
        Page<JobPosition> page = Pages.of(current, size);
        jobPositionMapper.selectPage(page, new LambdaQueryWrapper<JobPosition>()
                .eq(JobPosition::getCompanyId, company.getId())
                .orderByDesc(JobPosition::getUpdateTime)
                .orderByDesc(JobPosition::getId));
        return PageResult.of(page, toVos(page.getRecords()));
    }

    @Override
    public CompanyJobVO detail(Long id) {
        EntCompany company = companySupport.requireCurrent();
        JobPosition job = requireOwn(id, company.getId());
        return toVo(job, categoryName(job.getCategoryId()), tagsOf(job.getId()));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CompanyJobVO create(JobSaveDTO dto) {
        EntCompany company = companySupport.requireCurrent();
        JobCategory category = requireCategory(dto);
        List<Long> tagIds = requireTags(dto.getTagIds());
        assertSalary(dto);

        JobPosition job = new JobPosition();
        job.setCompanyId(company.getId());
        copyContent(dto, job, category.getName());
        job.setShelfStatus(0);
        job.setAuditStatus(0);
        job.setViewCount(0);
        job.setFavoriteCount(0);
        job.setApplyCount(0);
        job.setDeleted(0);
        jobPositionMapper.insert(job);
        replaceTags(job.getId(), tagIds);
        return toVo(job, category.getName(), tagsOf(job.getId()));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CompanyJobVO update(Long id, JobSaveDTO dto) {
        EntCompany company = companySupport.requireCurrent();
        JobPosition job = requireOwn(id, company.getId());
        JobCategory category = requireCategory(dto);
        List<Long> tagIds = requireTags(dto.getTagIds());
        assertSalary(dto);

        copyContent(dto, job, category.getName());
        job.setAuditStatus(0);
        jobPositionMapper.updateById(job);
        jobPositionMapper.update(null, new LambdaUpdateWrapper<JobPosition>()
                .eq(JobPosition::getId, job.getId())
                .setSql("audit_status = 0, audit_remark = NULL, audit_time = NULL, auditor_id = NULL"));
        job.setAuditStatus(0);
        job.setAuditRemark(null);
        job.setAuditTime(null);
        job.setAuditorId(null);
        replaceTags(job.getId(), tagIds);
        return toVo(job, category.getName(), tagsOf(job.getId()));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void shelf(Long id, JobShelfDTO dto) {
        EntCompany company = companySupport.requireCurrent();
        JobPosition job = requireOwn(id, company.getId());
        if (Integer.valueOf(1).equals(dto.getShelfStatus())) {
            // 未通过审核的企业或职位不能上架；下架（含草稿保存）不受限制
            if (!Integer.valueOf(1).equals(company.getAuditStatus())) {
                throw new BusinessException(403, "企业资质尚未通过审核，暂不能上架职位");
            }
            if (!Integer.valueOf(1).equals(job.getAuditStatus())) {
                throw new BusinessException(400, Integer.valueOf(2).equals(job.getAuditStatus())
                        ? "职位审核未通过，请按审核意见修改后重新提交审核"
                        : "职位尚未通过审核，审核通过后才能上架");
            }
        }
        job.setShelfStatus(dto.getShelfStatus());
        if (Integer.valueOf(1).equals(dto.getShelfStatus())) {
            job.setPublishTime(LocalDateTime.now());
        }
        jobPositionMapper.updateById(job);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(Long id) {
        EntCompany company = companySupport.requireCurrent();
        requireOwn(id, company.getId());
        jobPositionMapper.deleteById(id);
    }

    private JobPosition requireOwn(Long id, Long companyId) {
        JobPosition job = jobPositionMapper.selectById(id);
        if (job == null) {
            throw new BusinessException(404, "职位不存在");
        }
        if (!companyId.equals(job.getCompanyId())) {
            throw new BusinessException(403, "无权操作该职位");
        }
        return job;
    }

    private JobCategory requireCategory(JobSaveDTO dto) {
        JobCategory category = jobCategoryMapper.selectById(dto.getCategoryId());
        if (category == null || !Integer.valueOf(1).equals(category.getStatus())) {
            throw new BusinessException(400, "职位分类不存在或已停用");
        }
        return category;
    }

    /** 职位至少要有 1 个技能标签：推荐、相似职位与候选人匹配分都以它为锚点。 */
    private List<Long> requireTags(List<Long> raw) {
        List<Long> tagIds = raw == null ? List.of() : raw.stream().filter(Objects::nonNull).distinct().toList();
        if (tagIds.isEmpty()) {
            throw new BusinessException(400, "请至少选择 1 个技能标签");
        }
        if (tagIds.size() > 20) {
            throw new BusinessException(400, "技能标签最多选择 20 个");
        }
        List<SkillTag> tags = skillTagMapper.selectBatchIds(tagIds);
        boolean invalid = tags.size() != tagIds.size()
                || tags.stream().anyMatch(tag -> !Integer.valueOf(1).equals(tag.getStatus()));
        if (invalid) {
            throw new BusinessException(400, "技能标签不存在或已停用");
        }
        return tagIds;
    }

    private void assertSalary(JobSaveDTO dto) {
        if (dto.getSalaryMin() > dto.getSalaryMax()) {
            throw new BusinessException(400, "最低月薪不能高于最高月薪");
        }
    }

    private void copyContent(JobSaveDTO dto, JobPosition job, String techDirection) {
        job.setCategoryId(dto.getCategoryId());
        job.setTitle(dto.getTitle().trim());
        job.setTechDirection(techDirection);
        job.setProvince(dto.getProvince().trim());
        job.setCity(dto.getCity().trim());
        job.setDistrict(blankToEmpty(dto.getDistrict()));
        job.setAddress(blankToEmpty(dto.getAddress()));
        job.setSalaryMin(dto.getSalaryMin());
        job.setSalaryMax(dto.getSalaryMax());
        job.setSalaryMonths(dto.getSalaryMonths());
        job.setEducation(dto.getEducation());
        job.setExperienceReq(dto.getExperienceReq());
        job.setJobType(dto.getJobType());
        job.setHeadcount(dto.getHeadcount());
        job.setDescription(blankToEmpty(dto.getDescription()));
        job.setRequirement(blankToEmpty(dto.getRequirement()));
        job.setWelfare(blankToEmpty(dto.getWelfare()));
    }

    private void replaceTags(Long positionId, List<Long> tagIds) {
        Set<Long> wanted = new LinkedHashSet<>(tagIds);
        List<JobPositionTag> existing = jobPositionTagMapper.selectAllByPosition(positionId);
        Map<Long, JobPositionTag> byTag = new HashMap<>();
        for (JobPositionTag row : existing) {
            byTag.put(row.getTagId(), row);
        }
        for (JobPositionTag row : existing) {
            if (wanted.contains(row.getTagId())) {
                if (!Integer.valueOf(0).equals(row.getDeleted())) {
                    jobPositionTagMapper.restore(row.getId());
                }
                wanted.remove(row.getTagId());
            } else if (Integer.valueOf(0).equals(row.getDeleted())) {
                jobPositionTagMapper.deleteById(row.getId());
            }
        }
        for (Long tagId : wanted) {
            if (byTag.containsKey(tagId)) {
                continue;
            }
            JobPositionTag row = new JobPositionTag();
            row.setPositionId(positionId);
            row.setTagId(tagId);
            row.setDeleted(0);
            jobPositionTagMapper.insert(row);
        }
    }

    private List<PositionTagVO> tagsOf(Long positionId) {
        return positionTags.of(List.of(positionId)).getOrDefault(positionId, List.of());
    }

    private String categoryName(Long categoryId) {
        JobCategory category = jobCategoryMapper.selectById(categoryId);
        return category == null ? null : category.getName();
    }

    private List<CompanyJobVO> toVos(List<JobPosition> jobs) {
        if (jobs == null || jobs.isEmpty()) {
            return List.of();
        }
        List<Long> categoryIds = jobs.stream().map(JobPosition::getCategoryId).distinct().toList();
        Map<Long, String> categories = jobCategoryMapper.selectBatchIds(categoryIds).stream()
                .collect(Collectors.toMap(JobCategory::getId, JobCategory::getName, (a, b) -> a));
        Map<Long, List<PositionTagVO>> tags = positionTags.of(jobs.stream().map(JobPosition::getId).toList());
        List<CompanyJobVO> list = new ArrayList<>();
        for (JobPosition job : jobs) {
            list.add(toVo(job, categories.get(job.getCategoryId()), tags.getOrDefault(job.getId(), List.of())));
        }
        return list;
    }

    private CompanyJobVO toVo(JobPosition job, String categoryName, List<PositionTagVO> tags) {
        CompanyJobVO vo = new CompanyJobVO();
        vo.setId(job.getId());
        vo.setCompanyId(job.getCompanyId());
        vo.setCategoryId(job.getCategoryId());
        vo.setCategoryName(categoryName);
        vo.setTitle(job.getTitle());
        vo.setTechDirection(job.getTechDirection());
        vo.setProvince(job.getProvince());
        vo.setCity(job.getCity());
        vo.setDistrict(job.getDistrict());
        vo.setAddress(job.getAddress());
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
        vo.setPublishTime(job.getPublishTime());
        vo.setViewCount(job.getViewCount());
        vo.setFavoriteCount(job.getFavoriteCount());
        vo.setApplyCount(job.getApplyCount());
        vo.setCreateTime(job.getCreateTime());
        vo.setUpdateTime(job.getUpdateTime());
        vo.setTagIds(tags.stream().map(PositionTagVO::getTagId).toList());
        vo.setTagNames(tags.stream().map(PositionTagVO::getTagName).toList());
        return vo;
    }

    private String blankToEmpty(String value) {
        if (!StringUtils.hasText(value)) {
            return "";
        }
        return value.trim();
    }
}
