package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.vo.SparkRunVO;
import com.bishe.job.vo.SparkTaskLogVO;

import java.util.List;

public interface SparkAdminService {

    SparkRunVO run(List<String> tasks);

    PageResult<SparkTaskLogVO> tasks(String batchNo, Integer status, long current, long size);
}
