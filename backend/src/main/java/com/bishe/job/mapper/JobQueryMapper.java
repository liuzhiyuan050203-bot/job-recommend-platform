package com.bishe.job.mapper;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.dto.PublicJobQuery;
import com.bishe.job.vo.PositionTagVO;
import com.bishe.job.vo.PublicJobVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface JobQueryMapper {

    IPage<PublicJobVO> searchJobs(Page<PublicJobVO> page, @Param("q") PublicJobQuery query);

    PublicJobVO selectVisible(@Param("id") Long id);

    List<PositionTagVO> listTags(@Param("ids") List<Long> ids);
}
