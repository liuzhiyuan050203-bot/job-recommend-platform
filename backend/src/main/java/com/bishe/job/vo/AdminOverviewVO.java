package com.bishe.job.vo;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class AdminOverviewVO {

    private long jobTotal;
    private long jobPending;
    private long jobOnline;
    private long applicationTotal;
    private long companyTotal;
    private long studentTotal;
    private List<StatusCountVO> applicationStatusCounts = new ArrayList<>();

    @Data
    public static class StatusCountVO {
        private Integer status;
        private String statusName;
        private long count;
    }
}
