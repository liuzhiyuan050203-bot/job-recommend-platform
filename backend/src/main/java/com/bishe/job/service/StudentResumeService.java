package com.bishe.job.service;

import com.bishe.job.dto.ResumeSaveDTO;
import com.bishe.job.vo.ResumeVO;

import java.util.List;

public interface StudentResumeService {

    List<ResumeVO> list();

    ResumeVO detail(Long id);

    ResumeVO create(ResumeSaveDTO dto);

    ResumeVO update(Long id, ResumeSaveDTO dto);

    void setDefault(Long id);

    void delete(Long id);
}
