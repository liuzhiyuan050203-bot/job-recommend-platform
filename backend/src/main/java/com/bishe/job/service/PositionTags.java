package com.bishe.job.service;

import com.bishe.job.mapper.JobQueryMapper;
import com.bishe.job.vo.PositionTagVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@Component
@RequiredArgsConstructor
public class PositionTags {

    private final JobQueryMapper jobQueryMapper;

    public Map<Long, List<PositionTagVO>> of(Collection<Long> positionIds) {
        if (positionIds == null || positionIds.isEmpty()) {
            return Map.of();
        }
        List<Long> ids = positionIds.stream().filter(Objects::nonNull).distinct().toList();
        if (ids.isEmpty()) {
            return Map.of();
        }
        Map<Long, List<PositionTagVO>> grouped = new HashMap<>();
        for (PositionTagVO row : jobQueryMapper.listTags(ids)) {
            grouped.computeIfAbsent(row.getPositionId(), key -> new ArrayList<>()).add(row);
        }
        return grouped;
    }
}
