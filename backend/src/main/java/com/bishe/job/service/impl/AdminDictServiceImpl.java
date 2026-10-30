package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.dto.CategoryDTO;
import com.bishe.job.dto.SkillTagDTO;
import com.bishe.job.entity.JobCategory;
import com.bishe.job.entity.JobPosition;
import com.bishe.job.entity.SkillTag;
import com.bishe.job.mapper.JobCategoryMapper;
import com.bishe.job.mapper.JobPositionMapper;
import com.bishe.job.mapper.SkillTagMapper;
import com.bishe.job.service.AdminDictService;
import com.bishe.job.vo.CategoryVO;
import com.bishe.job.vo.SkillTagVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class AdminDictServiceImpl implements AdminDictService {

    private final JobCategoryMapper jobCategoryMapper;
    private final JobPositionMapper jobPositionMapper;
    private final SkillTagMapper skillTagMapper;

    @Override
    public List<CategoryVO> listCategories() {
        List<JobCategory> all = jobCategoryMapper.selectList(new LambdaQueryWrapper<JobCategory>()
                .orderByAsc(JobCategory::getSortNo)
                .orderByAsc(JobCategory::getId));

        Map<Long, CategoryVO> map = new HashMap<>();
        List<CategoryVO> roots = new ArrayList<>();

        for (JobCategory cat : all) {
            CategoryVO vo = new CategoryVO();
            vo.setId(cat.getId());
            vo.setParentId(cat.getParentId());
            vo.setName(cat.getName());
            vo.setSortNo(cat.getSortNo());
            vo.setStatus(cat.getStatus());
            map.put(cat.getId(), vo);
        }

        for (JobCategory cat : all) {
            CategoryVO vo = map.get(cat.getId());
            if (cat.getParentId() == null || !map.containsKey(cat.getParentId())) {
                roots.add(vo);
            } else {
                CategoryVO parent = map.get(cat.getParentId());
                parent.getChildren().add(vo);
            }
        }
        return roots;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void addCategory(CategoryDTO dto) {
        JobCategory category = new JobCategory();
        category.setParentId(dto.getParentId());
        category.setName(dto.getName().trim());
        category.setSortNo(dto.getSortNo() != null ? dto.getSortNo() : 0);
        category.setStatus(dto.getStatus() != null ? dto.getStatus() : 1);

        jobCategoryMapper.insert(category);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateCategory(Long id, CategoryDTO dto) {
        JobCategory category = jobCategoryMapper.selectById(id);
        if (category == null) {
            throw new BusinessException(404, "职位分类不存在");
        }

        category.setParentId(dto.getParentId());
        category.setName(dto.getName().trim());
        if (dto.getSortNo() != null) {
            category.setSortNo(dto.getSortNo());
        }
        if (dto.getStatus() != null) {
            category.setStatus(dto.getStatus());
        }

        jobCategoryMapper.updateById(category);
    }

    @Override
    public void deleteCategory(Long id) {
        JobCategory category = jobCategoryMapper.selectById(id);
        if (category == null) {
            throw new BusinessException(404, "职位分类不存在");
        }

        // 校验 1：是否存在子分类
        Long childCount = jobCategoryMapper.selectCount(new LambdaQueryWrapper<JobCategory>()
                .eq(JobCategory::getParentId, id));
        if (childCount > 0) {
            throw new BusinessException(400, "该分类下包含子分类，无法直接删除");
        }

        // 校验 2：是否被职位引用
        Long jobCount = jobPositionMapper.selectCount(new LambdaQueryWrapper<JobPosition>()
                .eq(JobPosition::getCategoryId, id));
        if (jobCount > 0) {
            throw new BusinessException(400, "已有职位引用该分类，无法删除");
        }

        jobCategoryMapper.deleteById(id);
    }

    @Override
    public PageResult<SkillTagVO> listSkillTags(String direction, String keyword, long current, long size) {
        Page<SkillTag> page = Pages.of(current, size);
        LambdaQueryWrapper<SkillTag> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(direction)) {
            wrapper.eq(SkillTag::getDirection, direction.trim());
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.like(SkillTag::getName, keyword.trim());
        }

        wrapper.orderByAsc(SkillTag::getSortNo).orderByAsc(SkillTag::getId);

        skillTagMapper.selectPage(page, wrapper);
        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, Collections.emptyList());
        }

        List<SkillTagVO> list = page.getRecords().stream().map(tag -> {
            SkillTagVO vo = new SkillTagVO();
            vo.setId(tag.getId());
            vo.setName(tag.getName());
            vo.setDirection(tag.getDirection());
            vo.setSortNo(tag.getSortNo());
            vo.setStatus(tag.getStatus());
            vo.setCreateTime(tag.getCreateTime());
            return vo;
        }).toList();

        return PageResult.of(page, list);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void addSkillTag(SkillTagDTO dto) {
        String name = dto.getName().trim();
        SkillTag existing = skillTagMapper.selectOne(new LambdaQueryWrapper<SkillTag>()
                .eq(SkillTag::getName, name));
        if (existing != null) {
            throw new BusinessException(400, "技能标签名称已存在");
        }

        SkillTag tag = new SkillTag();
        tag.setName(name);
        tag.setDirection(dto.getDirection().trim());
        tag.setSortNo(dto.getSortNo() != null ? dto.getSortNo() : 0);
        tag.setStatus(dto.getStatus() != null ? dto.getStatus() : 1);

        skillTagMapper.insert(tag);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateSkillTag(Long id, SkillTagDTO dto) {
        SkillTag tag = skillTagMapper.selectById(id);
        if (tag == null) {
            throw new BusinessException(404, "技能标签不存在");
        }

        String name = dto.getName().trim();
        SkillTag existing = skillTagMapper.selectOne(new LambdaQueryWrapper<SkillTag>()
                .eq(SkillTag::getName, name)
                .ne(SkillTag::getId, id));
        if (existing != null) {
            throw new BusinessException(400, "技能标签名称已存在");
        }

        tag.setName(name);
        tag.setDirection(dto.getDirection().trim());
        if (dto.getSortNo() != null) {
            tag.setSortNo(dto.getSortNo());
        }
        if (dto.getStatus() != null) {
            tag.setStatus(dto.getStatus());
        }

        skillTagMapper.updateById(tag);
    }

    @Override
    public void deleteSkillTag(Long id) {
        SkillTag tag = skillTagMapper.selectById(id);
        if (tag == null) {
            throw new BusinessException(404, "技能标签不存在");
        }
        skillTagMapper.deleteById(id);
    }
}
