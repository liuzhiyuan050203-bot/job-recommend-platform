package com.bishe.job.mapper;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.vo.RecommendJobVO;
import com.bishe.job.vo.RecommendMetricVO;
import com.bishe.job.vo.RecommendStatsVO;
import com.bishe.job.vo.SimilarJobVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface RecommendQueryMapper {

    int countLatest(@Param("userId") Long userId);

    IPage<RecommendJobVO> pageLatest(Page<RecommendJobVO> page, @Param("userId") Long userId);

    List<RecommendJobVO> fallback(@Param("userId") Long userId, @Param("limitSize") int limitSize);

    List<SimilarJobVO> similar(@Param("jobId") Long jobId, @Param("limitSize") int limitSize);

    List<RecommendMetricVO> latestEval();

    RecommendStatsVO latestStats();

    int countVisibleJobs();
}
