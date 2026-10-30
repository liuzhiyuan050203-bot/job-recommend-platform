package com.bishe.job.service;

import com.bishe.job.dto.StudentProfileUpdateDTO;
import com.bishe.job.dto.StudentSkillAddDTO;
import com.bishe.job.dto.StudentSkillUpdateDTO;
import com.bishe.job.vo.SkillVO;
import com.bishe.job.vo.StudentProfileVO;

import java.util.List;

public interface StudentProfileService {

    StudentProfileVO getProfile();

    void updateProfile(StudentProfileUpdateDTO dto);

    List<SkillVO> listSkills();

    void addSkill(StudentSkillAddDTO dto);

    void updateSkill(Long id, StudentSkillUpdateDTO dto);

    void deleteSkill(Long id);
}
