package com.bishe.job.dto;

import lombok.Data;

import java.util.List;

@Data
public class SparkRunDTO {

    /** 为空时执行 clean、aggregate、salary_regression。 */
    private List<String> tasks;
}
