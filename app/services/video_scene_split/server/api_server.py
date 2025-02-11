"""视频场景分割API服务器

该模块提供了一个基于Flask的RESTful API服务，用于处理视频场景分割任务。
主要功能包括：
- 接收视频文件路径
- 进行场景分割处理
- 返回分割结果，包括每个场景的起始帧和时间戳

依赖项：
- Flask: Web框架
- OpenCV (cv2): 视频处理
- scene_detection: 自定义场景分割模块

作者: MediaSymphony Team
日期: 2024-02
"""

from flask import Flask, request, jsonify
import os
import cv2
from core.scene_detection import SceneDetector
from werkzeug.utils import secure_filename
from utils.logger import Logger
from moviepy import VideoFileClip
import threading
from functools import partial
import time

app = Flask(__name__)
logger = Logger("scene_detection_api")

# 配置常量
SCENE_DETECTION_TIMEOUT = 1800  # 超时时间 1800s
VIDEO_CODEC = "libx264"  # 视频编码器

# 从配置文件获取允许的视频文件格式
ALLOWED_EXTENSIONS = {
    ext.split("/")[-1] for ext in ["video/mp4", "video/avi", "video/mov"]
}


def allowed_file(filename: str) -> bool:
    """检查文件是否为允许的视频格式

    Args:
        filename (str): 需要检查的文件名

    Returns:
        bool: 如果文件扩展名在允许列表中返回True，否则返回False
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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


def timeout_handler():
    raise TimeoutError("视频处理超时，请检查视频文件或调整超时时间设置")


def validate_request_data(data):
    """验证请求数据

    Args:
        data (dict): 请求数据

    Returns:
        tuple: (input_path, output_path, task_id, threshold, visualize)

    Raises:
        ValueError: 当请求数据无效时抛出异常
    """
    if not data:
        raise ValueError("请求体不能为空")

    # 验证必需参数
    required_fields = ["input_path", "output_path", "task_id"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValueError(f"缺少必需参数: {', '.join(missing_fields)}")

    # 获取请求参数
    input_path = data["input_path"]
    output_path = data["output_path"]
    task_id = data["task_id"]
    threshold = data.get("threshold", 0.5)
    visualize = data.get("visualize", False)

    # 验证视频文件是否存在
    if not os.path.exists(input_path):
        raise ValueError("视频文件不存在")

    # 验证视频文件格式
    if not allowed_file(input_path):
        raise ValueError("不支持的视频文件格式")

    return input_path, output_path, task_id, threshold, visualize


def detect_video_scenes(input_path: str, threshold: float):
    """检测视频场景

    Args:
        input_path (str): 视频文件路径
        threshold (float): 场景切换阈值

    Returns:
        tuple: (video_frames, scenes, single_frame_predictions, all_frame_predictions)
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise ValueError("无法打开视频文件")

    try:
        # 初始化场景检测器并执行处理
        logger.info("正在加载模型...")
        detector = SceneDetector()

        logger.info("正在处理视频...")
        # 获取视频的帧和预测结果
        video_frames, single_frame_predictions, all_frame_predictions = (
            detector.predict_video(input_path)
        )
        scenes = detector.predictions_to_scenes(
            single_frame_predictions, threshold=threshold
        )

        return video_frames, scenes, single_frame_predictions, all_frame_predictions
    finally:
        cap.release()


def write_video_segment(segment_clip, output_path, video_clip, retries=3, delay=1):
    """写入视频片段

    Args:
        segment_clip: VideoFileClip对象
        output_path (str): 输出文件路径
        video_clip: 原始视频片段
        retries (int): 重试次数
        delay (int): 重试延迟（秒）

    Returns:
        bool: 写入是否成功
    """
    for attempt in range(retries):
        try:
            # 获取原视频的编码参数
            original_bitrate = "8000k"
            if (
                segment_clip
                and hasattr(segment_clip.reader, "bitrate")
                and segment_clip.reader.bitrate
            ):
                original_bitrate = str(int(segment_clip.reader.bitrate)) + "k"

            cpu_count = os.cpu_count() or 4
            thread_count = max(1, cpu_count - 2)

            segment_clip.write_videofile(
                output_path,
                codec="libx264",
                fps=video_clip.fps,
                bitrate=original_bitrate,
                preset="medium",
                threads=thread_count,
                audio=True,
                logger=None,
            )
            return True
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
                continue
            raise


def process_video_segments(video_clip, scenes, output_path):
    """处理视频片段

    Args:
        video_clip: VideoFileClip对象
        scenes (list): 场景列表
        output_path (str): 输出目录路径

    Returns:
        list: 格式化的场景信息列表
    """
    formatted_scenes = []

    for i, (start, end) in enumerate(scenes):
        try:
            start_time = start / video_clip.fps
            end_time = end / video_clip.fps
            segment_clip = video_clip.subclip(start_time, end_time)

            # 为每个视频片段生成唯一文件名
            output_segment_path = os.path.join(output_path, f"segment_{i + 1}.mp4")
            write_video_segment(segment_clip, output_segment_path, video_clip)

            # 添加场景信息
            formatted_scenes.append(
                {
                    "start_frame": start,
                    "end_frame": end,
                    "start_time": format_time(start, video_clip.fps),
                    "end_time": format_time(end, video_clip.fps),
                }
            )


@app.route("/api/v1/scene-detection/process", methods=["POST"])
def process_scene_detection():
    """处理视频场景分割请求

    Returns:
        tuple: (response, status_code)
    """
    try:
        # 解析和验证请求数据
        data = request.get_json()
        input_path, output_path, task_id, threshold, visualize = validate_request_data(data)

        logger.info(
            "开始处理视频场景分割",
            {
                "task_id": task_id,
                "input_path": input_path,
                "output_path": output_path,
                "threshold": threshold,
                "visualize": visualize,
            },
        )

        # 创建输出目录
        os.makedirs(output_path, exist_ok=True)

        # 设置超时定时器
        timer = threading.Timer(SCENE_DETECTION_TIMEOUT, timeout_handler)
        timer.start()

        video_clip = None
        try:
            # 检测视频场景
            video_frames, scenes, single_frame_predictions, all_frame_predictions = detect_video_scenes(
                input_path, threshold
            )

            # 加载视频文件
            logger.info("正在切分场景...")
            try:
                video_clip = VideoFileClip(input_path)
                if not video_clip.reader or not hasattr(video_clip.reader, "fps"):
                    raise ValueError("无法正确加载视频文件，请检查视频格式是否正确")
            except Exception as e:
                logger.error(f"加载视频文件失败: {str(e)}")
                raise ValueError(f"加载视频文件失败: {str(e)}")

            # 处理视频片段
            formatted_scenes = process_video_segments(video_clip, scenes, output_path)

            # 如果需要可视化，生成预测结果的可视化图像
            if visualize:
                logger.info("正在生成预测可视化...")
                visualization = detector.visualize_predictions(
                    video_frames, [single_frame_predictions, all_frame_predictions]
                )
                visualization.save(f"{output_path}/predictions.png")

            logger.info(
                "处理完成",
                {
                    "task_id": task_id,
                    "scenes_count": len(scenes),
                    "output_dir": output_path,
                },
            )

            # 返回成功响应
            return jsonify(
                {
                    "status": "success",
                    "task_id": task_id,
                    "output_dir": output_path,
                    "scenes": formatted_scenes,
                }
            )

        finally:
            # 取消超时定时器
            timer.cancel()
            # 确保资源正确释放
            if video_clip is not None:
                video_clip.close()

    except TimeoutError as e:
        logger.error("处理超时", {"task_id": task_id, "error": str(e)})
        return jsonify({"error": str(e)}), 408
    except ValueError as e:
        error_msg = str(e)
        logger.error("请求参数无效", {"error": error_msg})
        return jsonify({"error": error_msg}), 400
    except Exception as e:
        error_msg = str(e)
        logger.error("处理过程中发生异常", {"task_id": task_id, "error": error_msg})
        return jsonify({"error": error_msg}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
