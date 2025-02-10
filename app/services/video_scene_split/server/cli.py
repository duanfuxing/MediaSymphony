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
from moviepy.editor import VideoFileClip
from core.scene_detection import SceneDetector


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


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="视频场景切分工具")
    parser.add_argument("--video", required=True, help="输入视频路径")
    parser.add_argument("--output", required=True, help="输出目录路径")
    parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help="TransNet V2 权重文件路径，如果未指定则尝试自动推断位置",
    )
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
    args = parser.parse_args()

    # 验证输入文件是否存在
    if not os.path.exists(args.video):
        print(f"错误：视频文件 '{args.video}' 不存在")
        sys.exit(1)

    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)

    try:
        print("正在加载模型...")
        detector = SceneDetector(args.weights)

        print("正在处理视频...")
        # 获取视频的帧和预测结果
        video_frames, single_frame_predictions, all_frame_predictions = (
            detector.predict_video(args.video)
        )
        scenes = detector.predictions_to_scenes(
            single_frame_predictions, threshold=args.threshold
        )

        # 加载视频文件
        print("正在切分场景...")
        video_clip = VideoFileClip(args.video)

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

            # 输出每个视频片段
            segment_clip.write_videofile(
                output_path, codec="libx264", fps=video_clip.fps, verbose=False
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
