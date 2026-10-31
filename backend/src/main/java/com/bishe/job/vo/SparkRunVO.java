package com.bishe.job.vo;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class SparkRunVO {

    private String batchNo;
    private List<String> tasks = new ArrayList<>();
    private String status;
}
