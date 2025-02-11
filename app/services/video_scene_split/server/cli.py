#!/usr/bin/env python3

"""视频场景分割命令行工具

该脚本提供命令行接口，用于执行视频场景分割任务。
使用方法：
    python cli.py --video <视频文件路径> --output <输出目录> [选项]

选项：
    --threshold: 场景切换阈值（默认0.5）

作者: MediaSymphony Team
日期: 2024-02
"""

import os
import sys
import argparse
import time
from moviepy import VideoFileClip
from core.scene_detection import SceneDetector
from utils.logger import Logger


def format_time(frame_number: int, fps: float) -> str:
    """将帧号转换为时间戳字符串

    Args:
        frame_number (int): 视频帧序号
        fps (float): 视频帧率

    Returns:
        str: 格式化的时间字符串，格式为"HH:MM:SS"
    """
    seconds = frame_number / fps
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class AudioMode:
    """音频处理模式"""

    MUTE = "mute"  # 静音模式
    UNMUTE = "un-mute"  # 非静音模式


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="视频场景切分工具")
    parser.add_argument("--input", required=True, help="输入视频路径")
    parser.add_argument("--output", required=True, help="输出目录路径")
    parser.add_argument("--taskid", help="自定义任务ID")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="场景切换阈值（默认0.5）",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="为每个提取的视频保存预测可视化的PNG文件",
    )
    parser.add_argument(
        "--audio-mode",
        choices=[AudioMode.MUTE, AudioMode.UNMUTE],
        default=AudioMode.UNMUTE,
        help="音频处理模式：mute（静音）或un-mute（保留音频，默认）",
    )
    args = parser.parse_args()

    # 验证输入文件是否存在
    if not os.path.exists(args.input):
        print(f"错误：视频文件 '{args.input}' 不存在")
        sys.exit(1)

    # 判断taskid是否存在
    if not args.taskid:
        args.taskid = str(int(time.time()))

    # 拼接输出目录 args.output/taskid
    args.output = os.path.join(args.output, args.taskid)

    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)

    try:
        # 初始化日志记录器
        logger = Logger("scene_detection_cli")
        logger.info("正在加载模型...")
        detector = SceneDetector(logger=logger)

        print("正在处理视频...")
        # 获取视频的帧和预测结果
        video_frames, single_frame_predictions, all_frame_predictions = (
            detector.predict_video(args.input)
        )
        scenes = detector.predictions_to_scenes(
            single_frame_predictions, threshold=args.threshold
        )

        # 加载视频文件
        print("正在切分场景...")
        video_clip = VideoFileClip(args.input)

        # 为每个切片生成独立的输出文件名
        for i, (start, end) in enumerate(scenes):
            start_time = start / video_clip.fps
            end_time = end / video_clip.fps
            segment_clip = video_clip.subclipped(start_time, end_time)

            # 为每个视频片段生成唯一文件名，输出到指定目录
            output_path = f"{args.output}/segment_{i + 1}.mp4"
            print(f"正在导出场景 {i + 1}/{len(scenes)}...")
            print(f"  开始时间: {format_time(start, video_clip.fps)}")
            print(f"  结束时间: {format_time(end, video_clip.fps)}")

            # 获取原视频的编码参数
            original_video_bitrate = "8000k"
            original_audio_bitrate = "192k"
            original_audio_codec = "aac"

            if video_clip.reader:
                if hasattr(video_clip.reader, "bitrate") and video_clip.reader.bitrate:
                    original_video_bitrate = str(int(video_clip.reader.bitrate)) + "k"
                if (
                    hasattr(video_clip.reader, "audio_bitrate")
                    and video_clip.reader.audio_bitrate
                ):
                    original_audio_bitrate = (
                        str(int(video_clip.reader.audio_bitrate)) + "k"
                    )
                if (
                    hasattr(video_clip.reader, "audio_codec")
                    and video_clip.reader.audio_codec
                ):
                    original_audio_codec = video_clip.reader.audio_codec

            # 获取CPU核心数并设置合适的线程数（保留1-2个核心给系统）
            cpu_count = os.cpu_count() or 4
            thread_count = max(1, cpu_count - 2)

            # 输出每个视频片段，使用原视频参数
            segment_clip.write_videofile(
                output_path,
                codec="libx264",  # 使用 libx264 编码器
                fps=video_clip.fps,
                bitrate=original_video_bitrate,  # 使用原视频码率
                preset="medium",  # 使用平衡的预设
                threads=thread_count,  # 动态设置线程数
                audio=args.audio_mode
                == AudioMode.UNMUTE,  # 根据音频处理模式决定是否包含音频
                audio_codec=(
                    original_audio_codec
                    if args.audio_mode == AudioMode.UNMUTE
                    else None
                ),  # 根据音频处理模式设置音频编码器
                audio_bitrate=(
                    original_audio_bitrate
                    if args.audio_mode == AudioMode.UNMUTE
                    else None
                ),  # 根据音频处理模式设置音频码率
                logger=None,  # 禁用moviepy的内部logger
            )

        # 如果需要可视化，生成预测结果的可视化图像
        if args.visualize:
            print("正在生成预测可视化...")
            visualization = detector.visualize_predictions(
                video_frames, [single_frame_predictions, all_frame_predictions]
            )
            visualization.save(f"{args.output}/predictions.png")

        # 关闭视频对象
        video_clip.close()

        print(f"\n处理完成！")
        print(f"共检测到 {len(scenes)} 个场景")
        print(f"输出目录: {args.output}")

    except Exception as e:
        print(f"\n错误：处理过程中发生异常: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
