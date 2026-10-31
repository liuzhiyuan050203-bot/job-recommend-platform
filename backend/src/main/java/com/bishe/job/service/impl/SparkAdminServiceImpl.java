package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.client.FastApiClient;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.entity.SparkTaskLog;
import com.bishe.job.mapper.SparkTaskLogMapper;
import com.bishe.job.service.SparkAdminService;
import com.bishe.job.vo.SparkRunVO;
import com.bishe.job.vo.SparkTaskLogVO;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class SparkAdminServiceImpl implements SparkAdminService {

    private static final Set<String> TASKS = Set.of("clean", "aggregate", "salary_regression");

    private final FastApiClient fastApiClient;
    private final SparkTaskLogMapper sparkTaskLogMapper;

    @Override
    public SparkRunVO run(List<String> tasks) {
        if (tasks != null) {
            for (String task : tasks) {
                if (!StringUtils.hasText(task) || !TASKS.contains(task.trim())) {
                    throw new BusinessException(400, "不支持的任务: " + task);
                }
            }
        }
        JsonNode data = fastApiClient.runSpark(tasks);
        SparkRunVO vo = new SparkRunVO();
        vo.setBatchNo(data.path("batchNo").asText(null));
        vo.setStatus(data.path("status").asText(null));
        List<String> names = new ArrayList<>();
        if (data.path("tasks").isArray()) {
            data.path("tasks").forEach(node -> names.add(node.asText()));
        }
        vo.setTasks(names);
        if (!StringUtils.hasText(vo.getBatchNo())) {
            throw new BusinessException(503, "分析服务不可用");
        }
        return vo;
    }

    @Override
    public PageResult<SparkTaskLogVO> tasks(String batchNo, Integer status, long current, long size) {
        Page<SparkTaskLog> page = Pages.of(current, size);
        LambdaQueryWrapper<SparkTaskLog> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(batchNo)) {
            wrapper.eq(SparkTaskLog::getBatchNo, batchNo.trim());
        }
        if (status != null) {
            wrapper.eq(SparkTaskLog::getStatus, status);
        }
        wrapper.orderByDesc(SparkTaskLog::getId);
        sparkTaskLogMapper.selectPage(page, wrapper);
        List<SparkTaskLogVO> records = new ArrayList<>();
        for (SparkTaskLog row : page.getRecords()) {
            records.add(toVO(row));
        }
        return PageResult.of(page, records);
    }

    private SparkTaskLogVO toVO(SparkTaskLog row) {
        SparkTaskLogVO vo = new SparkTaskLogVO();
        vo.setId(row.getId());
        vo.setBatchNo(row.getBatchNo());
        vo.setTaskCode(row.getTaskCode());
        vo.setTaskName(row.getTaskName());
        vo.setStatus(row.getStatus());
        vo.setStartTime(row.getStartTime());
        vo.setEndTime(row.getEndTime());
        vo.setInputCount(row.getInputCount());
        vo.setOutputCount(row.getOutputCount());
        vo.setResultMsg(row.getResultMsg());
        vo.setErrorMsg(row.getErrorMsg());
        vo.setParamsJson(row.getParamsJson());
        return vo;
    }
}
