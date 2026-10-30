package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.dto.AuditDTO;
import com.bishe.job.vo.AdminCompanyVO;

public interface AdminCompanyService {

    PageResult<AdminCompanyVO> listCompanies(Integer auditStatus, String keyword, long current, long size);

    AdminCompanyVO getCompany(Long id);

    void auditCompany(Long id, AuditDTO dto);
}
