package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.vo.RecommendEvalVO;
import com.bishe.job.vo.RecommendJobVO;
import com.bishe.job.vo.RecommendStatsVO;
import com.bishe.job.vo.SimilarJobVO;
import com.bishe.job.vo.SparkRunVO;

import java.util.List;

public interface RecommendService {

    PageResult<RecommendJobVO> pageForCurrentStudent(long current, long size);

    List<SimilarJobVO> similarJobs(Long jobId, long size);

    SparkRunVO run();

    RecommendEvalVO evaluation();

    RecommendStatsVO stats();
}
