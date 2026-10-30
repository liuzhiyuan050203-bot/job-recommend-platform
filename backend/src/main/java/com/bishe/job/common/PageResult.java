package com.bishe.job.common;

import com.baomidou.mybatisplus.core.metadata.IPage;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.Collections;
import java.util.List;

/**
 * 统一分页响应包装对象，严格包含 records, total, current, size
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PageResult<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 数据列表 */
    private List<T> records;

    /** 总记录数 */
    private long total;

    /** 当前页码 */
    private long current;

    /** 每页大小 */
    private long size;

    public static <T> PageResult<T> of(IPage<T> page) {
        if (page == null) {
            return empty(1, 10);
        }
        return new PageResult<>(page.getRecords(), page.getTotal(), page.getCurrent(), page.getSize());
    }

    public static <T, R> PageResult<R> of(IPage<T> page, List<R> records) {
        if (page == null) {
            return new PageResult<>(records, records != null ? records.size() : 0, 1, 10);
        }
        return new PageResult<>(records, page.getTotal(), page.getCurrent(), page.getSize());
    }

    public static <T> PageResult<T> empty(long current, long size) {
        return new PageResult<>(Collections.emptyList(), 0L, current, size);
    }
}
