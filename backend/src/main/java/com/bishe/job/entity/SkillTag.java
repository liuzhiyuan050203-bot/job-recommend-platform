package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 技能标签，对应 skill_tag
 */
@Data
@TableName("skill_tag")
public class SkillTag {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String name;

    /** 所属技术方向，如后端开发、前端开发、数据开发、人工智能 */
    private String direction;

    /** 排序号 */
    private Integer sortNo;

    /** 启用状态：0停用 1启用 */
    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
