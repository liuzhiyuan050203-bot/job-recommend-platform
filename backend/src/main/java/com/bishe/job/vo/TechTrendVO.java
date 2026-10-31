package com.bishe.job.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Data
public class TechTrendVO {

    private List<String> months = new ArrayList<>();
    private List<SeriesVO> series = new ArrayList<>();
    private List<RankVO> ranking = new ArrayList<>();

    @Data
    public static class SeriesVO {
        private String name;
        private List<Integer> data = new ArrayList<>();
    }

    @Data
    public static class RankVO {
        private String tagName;
        private String techDirection;
        private Integer demandCount;
        private BigDecimal avgSalary;
    }
}
