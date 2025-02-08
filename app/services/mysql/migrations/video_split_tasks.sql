-- 创建视频分割任务表
CREATE TABLE IF NOT EXISTS video_split_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT NOT NULL COMMENT '主键',
    uid VARCHAR(100) NOT NULL COMMENT '用户id',
    taskid VARCHAR(100) NOT NULL COMMENT '任务id',
    status VARCHAR(100) NOT NULL DEFAULT 'pending' COMMENT '任务状态(pending|processing|success|failed)',
    scene_cut_status VARCHAR(100) NOT NULL DEFAULT 'pending' COMMENT '场景分割步骤状态(pending|processing|success|failed)',
    audio_extract_status VARCHAR(100) NOT NULL DEFAULT 'pending' COMMENT '音频分离步骤状态(pending|processing|success|failed)',
    text_convert_status VARCHAR(100) NOT NULL DEFAULT 'pending' COMMENT '语音转写步骤状态(pending|processing|success|failed)',
    video_url VARCHAR(512) NOT NULL COMMENT '视频url',
    scene_cut_output JSON COMMENT '场景切割结果路径',
    audio_extract_output VARCHAR(512) COMMENT '音频路径',
    text_convert_output TEXT COMMENT '转写文本',
    error VARCHAR(512) COMMENT '错误信息',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_taskid (taskid),
    INDEX idx_uid (uid),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视频分割任务表';