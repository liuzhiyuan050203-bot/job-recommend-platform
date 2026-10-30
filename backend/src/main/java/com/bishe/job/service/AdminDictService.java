package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.dto.CategoryDTO;
import com.bishe.job.dto.SkillTagDTO;
import com.bishe.job.vo.CategoryVO;
import com.bishe.job.vo.SkillTagVO;

import java.util.List;

public interface AdminDictService {

    // 职位分类
    List<CategoryVO> listCategories();

    void addCategory(CategoryDTO dto);

    void updateCategory(Long id, CategoryDTO dto);

    void deleteCategory(Long id);

    // 技能标签
    PageResult<SkillTagVO> listSkillTags(String direction, String keyword, long current, long size);

    void addSkillTag(SkillTagDTO dto);

    void updateSkillTag(Long id, SkillTagDTO dto);

    void deleteSkillTag(Long id);
}
