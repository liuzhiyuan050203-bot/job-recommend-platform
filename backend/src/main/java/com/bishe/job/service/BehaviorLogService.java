package com.bishe.job.service;

import com.bishe.job.entity.UserBehaviorLog;
import com.bishe.job.mapper.UserBehaviorLogMapper;
import com.bishe.job.security.LoginUser;
import com.bishe.job.security.RoleCodes;
import com.bishe.job.security.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

/**
 * 记录学生隐式反馈。权重：浏览 1、收藏 3、投递 5。非学生不记。
 */
@Service
@RequiredArgsConstructor
public class BehaviorLogService {

    public static final int VIEW = 1;
    public static final int FAVORITE = 2;
    public static final int APPLY = 3;

    private final UserBehaviorLogMapper userBehaviorLogMapper;

    public void logJob(int behaviorType, Long jobId) {
        LoginUser user = UserContext.get();
        if (user == null || user.getId() == null || !Integer.valueOf(RoleCodes.STUDENT).equals(user.getRole())) {
            return;
        }
        int weight = switch (behaviorType) {
            case FAVORITE -> 3;
            case APPLY -> 5;
            default -> 1;
        };
        UserBehaviorLog row = new UserBehaviorLog();
        row.setUserId(user.getId());
        row.setBehaviorType(behaviorType);
        row.setTargetType(1);
        row.setTargetId(jobId);
        row.setWeight(weight);
        row.setDeleted(0);
        userBehaviorLogMapper.insert(row);
    }
}
