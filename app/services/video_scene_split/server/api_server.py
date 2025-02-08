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
from core.scene_detection import process_video
from werkzeug.utils import secure_filename

app = Flask(__name__)

# 配置文件上传和输出目录
UPLOAD_FOLDER = "videos/uploads"  # 上传文件临时存储目录
OUTPUT_FOLDER = "videos/outputs"  # 处理结果输出目录
ALLOWED_EXTENSIONS = {"mp4", "avi", "mov"}  # 允许的视频文件格式


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


@app.route("/api/v1/scene-detection/process", methods=["POST"])
def process_scene_detection():
    """处理视频场景分割请求

    接收POST请求，包含视频文件路径和可选参数，执行场景分割处理并返回结果。

    请求体JSON格式：
    {
        "video_path": "视频文件路径",
        "task_id": "任务ID（可选）",
        "threshold": 0.35,  # 场景切换阈值（可选）
        "min_scene_length": 15  # 最小场景长度（帧数，可选）
    }

    Returns:
        JSON响应：
        成功：
        {
            "status": "success",
            "task_id": "任务ID",
            "output_dir": "输出目录路径",
            "scenes": [
                {
                    "start_frame": 0,
                    "end_frame": 120,
                    "start_time": "00:00:00",
                    "end_time": "00:00:05"
                }
            ]
        }
        失败：
        {
            "error": "错误信息"
        }
    """
    # 解析请求数据
    data = request.get_json()
    if not data or "video_path" not in data:
        return jsonify({"error": "视频路径未提供"}), 400

    # 获取请求参数
    video_path = data["video_path"]
    task_id = data.get("task_id")  # 可选参数
    threshold = data.get("threshold", 0.35)  # 场景切换阈值，默认0.35
    min_scene_length = data.get("min_scene_length", 15)  # 最小场景长度，默认15帧

    # 验证视频文件是否存在
    if not os.path.exists(video_path):
        return jsonify({"error": "视频文件不存在"}), 400

    # 创建输出目录
    output_dir = os.path.join(
        OUTPUT_FOLDER, os.path.basename(video_path).rsplit(".", 1)[0]
    )
    os.makedirs(output_dir, exist_ok=True)

    try:
        # 获取视频FPS用于时间戳计算
        import cv2

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        # 执行视频场景分割处理
        scenes = process_video(video_path, output_dir)

        # 格式化场景信息，添加帧号和时间戳
        formatted_scenes = []
        for start, end in scenes:
            formatted_scenes.append(
                {
                    "start_frame": int(start),
                    "end_frame": int(end),
                    "start_time": format_time(start, fps),
                    "end_time": format_time(end, fps),
                }
            )

        # 返回成功响应
        return jsonify(
            {
                "status": "success",
                "task_id": task_id,
                "output_dir": output_dir,
                "scenes": formatted_scenes,
            }
        )
    except Exception as e:
        # 处理过程中的错误
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    app.run(host="0.0.0.0", port=5000)
