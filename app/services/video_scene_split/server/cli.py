#!/usr/bin/env python3

"""视频场景分割命令行工具

该脚本提供命令行接口，用于执行视频场景分割任务。
使用方法：
    python cli.py --video <视频文件路径> --output <输出目录> [选项]

选项：
    --threshold: 场景切换阈值（默认0.5）
    --batch-size: 批处理大小（默认32）
    --min-scene-length: 最小场景长度（帧数，默认15）

作者: MediaSymphony Team
日期: 2024-02
"""

import os
import sys
import argparse
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
    parser = argparse.ArgumentParser(description="视频场景分割命令行工具")
    parser.add_argument("--video", required=True, help="输入视频文件路径")
    parser.add_argument("--output", required=True, help="输出目录路径")
    parser.add_argument(
        "--threshold", type=float, default=0.5, help="场景切换阈值（默认0.5）"
    )
    parser.add_argument(
        "--batch-size", type=int, default=32, help="批处理大小（默认32）"
    )
    parser.add_argument(
        "--min-scene-length", type=int, default=15, help="最小场景长度（帧数，默认15）"
    )
    parser.add_argument("--model-path", type=str, help="模型路径（可选）")

    args = parser.parse_args()

    # 验证输入文件是否存在
    if not os.path.exists(args.video):
        print(f"错误：视频文件 '{args.video}' 不存在")
        sys.exit(1)

    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)

    try:
        # 初始化场景检测器
        detector = SceneDetector(model_path=args.model_path)

        # 获取视频FPS用于时间戳计算
        import cv2

        cap = cv2.VideoCapture(args.video)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        # 执行场景分割
        print(f"\n开始处理视频: {args.video}")
        scenes = detector.process_video(
            args.video, args.output, batch_size=args.batch_size
        )

        # 打印场景信息
        print(f"\n检测到 {len(scenes)} 个场景:")
        for i, (start, end) in enumerate(scenes, 1):
            start_time = format_time(start, fps)
            end_time = format_time(end, fps)
            duration = format_time(end - start, fps)
            print(
                f"场景 {i:3d}: {start_time} - {end_time} (持续时间: {duration}, 帧范围: {start}-{end})"
            )

        print(f"\n处理完成！输出目录: {args.output}")

    except Exception as e:
        print(f"\n错误：处理过程中发生异常: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
