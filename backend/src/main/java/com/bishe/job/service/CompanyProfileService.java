package com.bishe.job.service;

import com.bishe.job.dto.CompanyProfileUpdateDTO;
import com.bishe.job.dto.CompanyQualificationDTO;
import com.bishe.job.vo.CompanyProfileVO;

public interface CompanyProfileService {

    CompanyProfileVO getProfile();

    void updateProfile(CompanyProfileUpdateDTO dto);

    void submitQualification(CompanyQualificationDTO dto);
}
