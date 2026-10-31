package com.bishe.job.vo;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

/**
 * 近若干月的职位发布量与投递量。没有数据的月份计数为 0，三个列表等长且按下标对齐。
 */
@Data
public class HiringDemandVO {

    private List<String> months = new ArrayList<>();
    private List<Long> jobCounts = new ArrayList<>();
    private List<Long> applyCounts = new ArrayList<>();
}
