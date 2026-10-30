package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.vo.PublicJobVO;

public interface StudentFavoriteService {

    void add(Long jobId);

    void remove(Long jobId);

    PageResult<PublicJobVO> page(long current, long size);
}
