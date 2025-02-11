-- 创建视频分割任务表
CREATE TABLE IF NOT EXISTS video_split_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT NOT NULL COMMENT '主键',
    uid VARCHAR(100) NOT NULL COMMENT '用户id',
    taskid VARCHAR(100) NOT NULL COMMENT '任务id',
    status VARCHAR(100) NOT NULL DEFAULT 'pending' COMMENT '主任务状态(pending|processing|completed|failed)',
    task_progress JSON NOT NULL DEFAULT (JSON_OBJECT(
        'scene_cut', JSON_OBJECT('status', 'pending', 'output', NULL),
        'audio_extract', JSON_OBJECT('status', 'pending', 'output', NULL),
        'text_convert', JSON_OBJECT('status', 'pending', 'output', NULL)
    )) COMMENT '子任务进度(包含状态和输出)',
    video_url VARCHAR(512) NOT NULL COMMENT '视频url',
    error JSON COMMENT '错误信息(主任务和子任务)',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_taskid (taskid),
    INDEX idx_uid (uid),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视频分割任务表';