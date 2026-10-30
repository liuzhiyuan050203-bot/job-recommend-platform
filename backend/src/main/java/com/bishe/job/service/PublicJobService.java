package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.dto.PublicJobQuery;
import com.bishe.job.vo.PublicJobVO;

import java.util.List;

public interface PublicJobService {

    /**
     * 学历筛选采用「职位学历要求 &lt;= 传入学历」。
     * 0 表示不限且数值最小，传入 0 只命中不限；传入本科 2 会命中不限、专科和本科。
     */
    PageResult<PublicJobVO> search(PublicJobQuery query, long current, long size);

    PublicJobVO detail(Long id);

    List<Long> parseTagIds(List<String> raw);
}
