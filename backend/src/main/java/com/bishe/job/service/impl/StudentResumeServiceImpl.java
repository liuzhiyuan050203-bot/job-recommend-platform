package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.bishe.job.common.BusinessException;
import com.bishe.job.dto.ResumeSaveDTO;
import com.bishe.job.entity.StuResume;
import com.bishe.job.mapper.StuResumeMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.StudentResumeService;
import com.bishe.job.vo.ResumeVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.List;

@Service
@RequiredArgsConstructor
public class StudentResumeServiceImpl implements StudentResumeService {

    private final StuResumeMapper stuResumeMapper;

    @Override
    public List<ResumeVO> list() {
        Long userId = UserContext.require().getId();
        return stuResumeMapper.selectList(new LambdaQueryWrapper<StuResume>()
                        .eq(StuResume::getUserId, userId)
                        .orderByDesc(StuResume::getIsDefault)
                        .orderByDesc(StuResume::getId))
                .stream().map(this::toVo).toList();
    }

    @Override
    public ResumeVO detail(Long id) {
        return toVo(requireOwn(id));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ResumeVO create(ResumeSaveDTO dto) {
        Long userId = UserContext.require().getId();
        Long count = stuResumeMapper.selectCount(new LambdaQueryWrapper<StuResume>().eq(StuResume::getUserId, userId));
        boolean makeDefault = Integer.valueOf(1).equals(dto.getIsDefault()) || count == null || count == 0;
        if (makeDefault) {
            clearDefault(userId);
        }
        StuResume resume = new StuResume();
        resume.setUserId(userId);
        fill(dto, resume);
        resume.setIsDefault(makeDefault ? 1 : 0);
        resume.setDeleted(0);
        stuResumeMapper.insert(resume);
        return toVo(resume);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ResumeVO update(Long id, ResumeSaveDTO dto) {
        StuResume resume = requireOwn(id);
        fill(dto, resume);
        stuResumeMapper.updateById(resume);
        if (Integer.valueOf(1).equals(dto.getIsDefault())) {
            setDefault(id);
            resume.setIsDefault(1);
        }
        return toVo(stuResumeMapper.selectById(id));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void setDefault(Long id) {
        StuResume resume = requireOwn(id);
        clearDefault(resume.getUserId());
        stuResumeMapper.update(null, new LambdaUpdateWrapper<StuResume>()
                .eq(StuResume::getId, resume.getId())
                .set(StuResume::getIsDefault, 1));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(Long id) {
        requireOwn(id);
        stuResumeMapper.deleteById(id);
    }

    private void clearDefault(Long userId) {
        stuResumeMapper.update(null, new LambdaUpdateWrapper<StuResume>()
                .eq(StuResume::getUserId, userId)
                .set(StuResume::getIsDefault, 0));
    }

    private StuResume requireOwn(Long id) {
        StuResume resume = stuResumeMapper.selectById(id);
        if (resume == null) {
            throw new BusinessException(404, "简历不存在");
        }
        if (!UserContext.require().getId().equals(resume.getUserId())) {
            throw new BusinessException(403, "无权操作该简历");
        }
        return resume;
    }

    private void fill(ResumeSaveDTO dto, StuResume resume) {
        resume.setTitle(dto.getTitle().trim());
        resume.setEducationExp(blank(dto.getEducationExp()));
        resume.setProjectExp(blank(dto.getProjectExp()));
        resume.setInternshipExp(blank(dto.getInternshipExp()));
        resume.setSkillDesc(blank(dto.getSkillDesc()));
        resume.setSelfEvaluation(blank(dto.getSelfEvaluation()));
        resume.setAttachmentUrl(blank(dto.getAttachmentUrl()));
    }

    private String blank(String value) {
        return StringUtils.hasText(value) ? value.trim() : "";
    }

    private ResumeVO toVo(StuResume resume) {
        ResumeVO vo = new ResumeVO();
        vo.setId(resume.getId());
        vo.setUserId(resume.getUserId());
        vo.setTitle(resume.getTitle());
        vo.setIsDefault(resume.getIsDefault());
        vo.setEducationExp(resume.getEducationExp());
        vo.setProjectExp(resume.getProjectExp());
        vo.setInternshipExp(resume.getInternshipExp());
        vo.setSkillDesc(resume.getSkillDesc());
        vo.setSelfEvaluation(resume.getSelfEvaluation());
        vo.setAttachmentUrl(resume.getAttachmentUrl());
        vo.setCreateTime(resume.getCreateTime());
        vo.setUpdateTime(resume.getUpdateTime());
        return vo;
    }
}
