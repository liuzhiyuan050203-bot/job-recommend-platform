package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bishe.job.common.BusinessException;
import com.bishe.job.dto.StudentProfileUpdateDTO;
import com.bishe.job.dto.StudentSkillAddDTO;
import com.bishe.job.dto.StudentSkillUpdateDTO;
import com.bishe.job.entity.SkillTag;
import com.bishe.job.entity.StuProfile;
import com.bishe.job.entity.StuSkill;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.SkillTagMapper;
import com.bishe.job.mapper.StuProfileMapper;
import com.bishe.job.mapper.StuSkillMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.StudentProfileService;
import com.bishe.job.vo.SkillVO;
import com.bishe.job.vo.StudentProfileVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class StudentProfileServiceImpl implements StudentProfileService {

    private final StuProfileMapper stuProfileMapper;
    private final StuSkillMapper stuSkillMapper;
    private final SkillTagMapper skillTagMapper;
    private final SysUserMapper sysUserMapper;

    @Override
    public StudentProfileVO getProfile() {
        Long userId = UserContext.get().getId();
        StuProfile profile = stuProfileMapper.selectOne(new LambdaQueryWrapper<StuProfile>()
                .eq(StuProfile::getUserId, userId));
        if (profile == null) {
            StudentProfileVO vo = new StudentProfileVO();
            vo.setUserId(userId);
            return vo;
        }
        return toVO(profile);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateProfile(StudentProfileUpdateDTO dto) {
        Long userId = UserContext.get().getId();

        // 校验薪资区间
        if (dto.getExpectSalaryMin() != null && dto.getExpectSalaryMax() != null) {
            if (dto.getExpectSalaryMax() < dto.getExpectSalaryMin()) {
                throw new BusinessException(400, "期望月薪上限不能低于下限");
            }
        }

        // 校验学号唯一性
        if (StringUtils.hasText(dto.getStudentNo())) {
            StuProfile existingWithNo = stuProfileMapper.selectOne(new LambdaQueryWrapper<StuProfile>()
                    .eq(StuProfile::getStudentNo, dto.getStudentNo().trim())
                    .ne(StuProfile::getUserId, userId));
            if (existingWithNo != null) {
                throw new BusinessException(400, "该学号已被其他学生登记");
            }
        }

        StuProfile profile = stuProfileMapper.selectOne(new LambdaQueryWrapper<StuProfile>()
                .eq(StuProfile::getUserId, userId));
        boolean isNew = false;
        if (profile == null) {
            profile = new StuProfile();
            profile.setUserId(userId);
            isNew = true;
        }

        profile.setRealName(dto.getRealName().trim());
        profile.setGender(dto.getGender());
        profile.setBirthday(dto.getBirthday());
        profile.setStudentNo(StringUtils.hasText(dto.getStudentNo()) ? dto.getStudentNo().trim() : null);
        profile.setSchool(dto.getSchool());
        profile.setCollege(dto.getCollege());
        profile.setMajor(dto.getMajor());
        profile.setEducation(dto.getEducation());
        profile.setGraduationYear(dto.getGraduationYear());
        profile.setExpectCity(dto.getExpectCity());
        profile.setExpectSalaryMin(dto.getExpectSalaryMin());
        profile.setExpectSalaryMax(dto.getExpectSalaryMax());
        profile.setExpectDirection(dto.getExpectDirection());
        profile.setSelfIntro(dto.getSelfIntro());

        if (isNew) {
            stuProfileMapper.insert(profile);
        } else {
            stuProfileMapper.updateById(profile);
        }

        // 同步更新用户昵称
        SysUser user = sysUserMapper.selectById(userId);
        if (user != null) {
            user.setNickname(dto.getRealName().trim());
            sysUserMapper.updateById(user);
        }
    }

    @Override
    public List<SkillVO> listSkills() {
        Long userId = UserContext.get().getId();
        List<StuSkill> skills = stuSkillMapper.selectList(new LambdaQueryWrapper<StuSkill>()
                .eq(StuSkill::getUserId, userId)
                .orderByDesc(StuSkill::getProficiency));
        if (skills.isEmpty()) {
            return Collections.emptyList();
        }

        List<Long> tagIds = skills.stream().map(StuSkill::getTagId).distinct().toList();
        List<SkillTag> tags = skillTagMapper.selectBatchIds(tagIds);
        Map<Long, SkillTag> tagMap = tags.stream().collect(Collectors.toMap(SkillTag::getId, t -> t));

        List<SkillVO> result = new ArrayList<>();
        for (StuSkill skill : skills) {
            SkillVO vo = new SkillVO();
            vo.setId(skill.getId());
            vo.setTagId(skill.getTagId());
            vo.setProficiency(skill.getProficiency());
            SkillTag tag = tagMap.get(skill.getTagId());
            if (tag != null) {
                vo.setTagName(tag.getName());
                vo.setDirection(tag.getDirection());
            } else {
                vo.setTagName("未知技能");
                vo.setDirection("其他");
            }
            result.add(vo);
        }
        return result;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void addSkill(StudentSkillAddDTO dto) {
        Long userId = UserContext.get().getId();
        SkillTag tag = null;
        if (dto.getSkillTagId() != null) {
            tag = skillTagMapper.selectById(dto.getSkillTagId());
            if (tag == null) {
                throw new BusinessException(400, "指定的技能标签不存在");
            }
        } else if (StringUtils.hasText(dto.getTagName())) {
            String name = dto.getTagName().trim();
            tag = skillTagMapper.selectOne(new LambdaQueryWrapper<SkillTag>()
                    .eq(SkillTag::getName, name));
            if (tag == null) {
                tag = new SkillTag();
                tag.setName(name);
                tag.setDirection(StringUtils.hasText(dto.getDirection()) ? dto.getDirection() : "综合技术");
                tag.setSortNo(100);
                tag.setStatus(1);
                skillTagMapper.insert(tag);
            }
        } else {
            throw new BusinessException(400, "请提供技能标签编号或技能名称");
        }

        // 检查是否已有该技能（包含逻辑删除的记录）
        StuSkill existing = stuSkillMapper.selectWithDeleted(userId, tag.getId());
        if (existing != null) {
            stuSkillMapper.restoreSkill(existing.getId(), dto.getProficiency());
        } else {
            StuSkill skill = new StuSkill();
            skill.setUserId(userId);
            skill.setTagId(tag.getId());
            skill.setProficiency(dto.getProficiency());
            stuSkillMapper.insert(skill);
        }
    }

    @Override
    public void updateSkill(Long id, StudentSkillUpdateDTO dto) {
        Long userId = UserContext.get().getId();
        StuSkill skill = stuSkillMapper.selectById(id);
        if (skill == null || !skill.getUserId().equals(userId)) {
            throw new BusinessException(404, "技能记录不存在或无权操作");
        }
        skill.setProficiency(dto.getProficiency());
        stuSkillMapper.updateById(skill);
    }

    @Override
    public void deleteSkill(Long id) {
        Long userId = UserContext.get().getId();
        StuSkill skill = stuSkillMapper.selectById(id);
        if (skill == null || !skill.getUserId().equals(userId)) {
            throw new BusinessException(404, "技能记录不存在或无权操作");
        }
        stuSkillMapper.deleteById(id);
    }

    private StudentProfileVO toVO(StuProfile profile) {
        StudentProfileVO vo = new StudentProfileVO();
        vo.setId(profile.getId());
        vo.setUserId(profile.getUserId());
        vo.setRealName(profile.getRealName());
        vo.setGender(profile.getGender());
        Integer g = profile.getGender();
        vo.setGenderName(Integer.valueOf(1).equals(g) ? "男" : (Integer.valueOf(2).equals(g) ? "女" : "未知"));
        vo.setBirthday(profile.getBirthday());
        vo.setStudentNo(profile.getStudentNo());
        vo.setSchool(profile.getSchool());
        vo.setCollege(profile.getCollege());
        vo.setMajor(profile.getMajor());
        vo.setEducation(profile.getEducation());
        vo.setEducationName(educationName(profile.getEducation()));
        vo.setGraduationYear(profile.getGraduationYear());
        vo.setExpectCity(profile.getExpectCity());
        vo.setExpectSalaryMin(profile.getExpectSalaryMin());
        vo.setExpectSalaryMax(profile.getExpectSalaryMax());
        vo.setExpectDirection(profile.getExpectDirection());
        vo.setSelfIntro(profile.getSelfIntro());
        return vo;
    }

    private String educationName(Integer education) {
        if (education == null) return "未知";
        return switch (education) {
            case 1 -> "专科";
            case 2 -> "本科";
            case 3 -> "硕士";
            case 4 -> "博士";
            default -> "未知";
        };
    }
}
