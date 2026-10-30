package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.dto.JobSaveDTO;
import com.bishe.job.dto.JobShelfDTO;
import com.bishe.job.vo.CompanyJobVO;

public interface CompanyJobService {

    PageResult<CompanyJobVO> page(long current, long size);

    CompanyJobVO detail(Long id);

    CompanyJobVO create(JobSaveDTO dto);

    CompanyJobVO update(Long id, JobSaveDTO dto);

    void shelf(Long id, JobShelfDTO dto);

    void delete(Long id);
}
