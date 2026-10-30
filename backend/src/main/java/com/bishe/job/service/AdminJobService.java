package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.dto.AuditDTO;
import com.bishe.job.vo.AdminJobVO;

public interface AdminJobService {

    PageResult<AdminJobVO> listJobs(Integer auditStatus, String keyword, long current, long size);

    void auditJob(Long id, AuditDTO dto);
}
