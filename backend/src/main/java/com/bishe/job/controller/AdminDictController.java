package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.CategoryDTO;
import com.bishe.job.dto.SkillTagDTO;
import com.bishe.job.service.AdminDictService;
import com.bishe.job.vo.CategoryVO;
import com.bishe.job.vo.SkillTagVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class AdminDictController {

    private final AdminDictService adminDictService;

    // --- 职位分类管理 ---

    @GetMapping("/categories")
    public Result<List<CategoryVO>> listCategories() {
        return Result.success(adminDictService.listCategories());
    }

    @PostMapping("/categories")
    public Result<Void> addCategory(@Valid @RequestBody CategoryDTO dto) {
        adminDictService.addCategory(dto);
        return Result.success("职位分类添加成功", null);
    }

    @PutMapping("/categories/{id}")
    public Result<Void> updateCategory(@PathVariable("id") Long id,
                                       @Valid @RequestBody CategoryDTO dto) {
        adminDictService.updateCategory(id, dto);
        return Result.success("职位分类更新成功", null);
    }

    @DeleteMapping("/categories/{id}")
    public Result<Void> deleteCategory(@PathVariable("id") Long id) {
        adminDictService.deleteCategory(id);
        return Result.success("职位分类删除成功", null);
    }

    // --- 技能标签字典管理 ---

    @GetMapping("/skill-tags")
    public Result<PageResult<SkillTagVO>> listSkillTags(
            @RequestParam(value = "direction", required = false) String direction,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(adminDictService.listSkillTags(direction, keyword, current, size));
    }

    @PostMapping("/skill-tags")
    public Result<Void> addSkillTag(@Valid @RequestBody SkillTagDTO dto) {
        adminDictService.addSkillTag(dto);
        return Result.success("技能标签添加成功", null);
    }

    @PutMapping("/skill-tags/{id}")
    public Result<Void> updateSkillTag(@PathVariable("id") Long id,
                                       @Valid @RequestBody SkillTagDTO dto) {
        adminDictService.updateSkillTag(id, dto);
        return Result.success("技能标签更新成功", null);
    }

    @DeleteMapping("/skill-tags/{id}")
    public Result<Void> deleteSkillTag(@PathVariable("id") Long id) {
        adminDictService.deleteSkillTag(id);
        return Result.success("技能标签删除成功", null);
    }
}
