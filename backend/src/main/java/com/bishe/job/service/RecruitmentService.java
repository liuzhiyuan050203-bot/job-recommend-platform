package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.dto.ApplicationCreateDTO;
import com.bishe.job.dto.ApplicationStatusDTO;
import com.bishe.job.dto.InterviewNoticeDTO;
import com.bishe.job.dto.InterviewResultDTO;
import com.bishe.job.vo.AdminOverviewVO;
import com.bishe.job.vo.ApplicationDetailVO;
import com.bishe.job.vo.ApplicationItemVO;
import com.bishe.job.vo.InterviewVO;

import java.util.List;

public interface RecruitmentService {

    Long apply(ApplicationCreateDTO dto);

    PageResult<ApplicationItemVO> studentPage(Integer status, long current, long size);

    ApplicationDetailVO studentDetail(Long id);

    List<InterviewVO> upcomingInterviews();

    PageResult<ApplicationItemVO> companyPage(Long jobId, Integer status, String keyword, long current, long size);

    ApplicationDetailVO companyDetail(Long id);

    void changeStatus(Long id, ApplicationStatusDTO dto);

    Long sendNotice(Long id, InterviewNoticeDTO dto);

    PageResult<InterviewVO> companyInterviews(Integer interviewStatus, long current, long size);

    void saveInterviewResult(Long id, InterviewResultDTO dto);

    PageResult<ApplicationItemVO> adminPage(Integer status, Long companyId, Long jobId, String keyword,
                                             long current, long size);

    AdminOverviewVO overview();
}
