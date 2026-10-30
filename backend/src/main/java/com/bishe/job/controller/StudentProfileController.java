package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.dto.StudentProfileUpdateDTO;
import com.bishe.job.dto.StudentSkillAddDTO;
import com.bishe.job.dto.StudentSkillUpdateDTO;
import com.bishe.job.service.StudentProfileService;
import com.bishe.job.vo.SkillVO;
import com.bishe.job.vo.StudentProfileVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/student")
@RequiredArgsConstructor
public class StudentProfileController {

    private final StudentProfileService studentProfileService;

    @GetMapping("/profile")
    public Result<StudentProfileVO> getProfile() {
        return Result.success(studentProfileService.getProfile());
    }

    @PutMapping("/profile")
    public Result<Void> updateProfile(@Valid @RequestBody StudentProfileUpdateDTO dto) {
        studentProfileService.updateProfile(dto);
        return Result.success("个人档案保存成功", null);
    }

    @GetMapping("/skills")
    public Result<List<SkillVO>> listSkills() {
        return Result.success(studentProfileService.listSkills());
    }

    @PostMapping("/skills")
    public Result<Void> addSkill(@Valid @RequestBody StudentSkillAddDTO dto) {
        studentProfileService.addSkill(dto);
        return Result.success("技能添加成功", null);
    }

    @PutMapping("/skills/{id}")
    public Result<Void> updateSkill(@PathVariable("id") Long id,
                                   @Valid @RequestBody StudentSkillUpdateDTO dto) {
        studentProfileService.updateSkill(id, dto);
        return Result.success("技能熟练度更新成功", null);
    }

    @DeleteMapping("/skills/{id}")
    public Result<Void> deleteSkill(@PathVariable("id") Long id) {
        studentProfileService.deleteSkill(id);
        return Result.success("技能删除成功", null);
    }
}
