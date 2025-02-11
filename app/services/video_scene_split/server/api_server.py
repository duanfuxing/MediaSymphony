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
from core.scene_detection import SceneDetector
from werkzeug.utils import secure_filename
from utils.logger import Logger
from moviepy import VideoFileClip
import signal
from functools import partial

app = Flask(__name__)
logger = Logger("scene_detection_api")

# 从配置文件获取超时时间 1800s
SCENE_DETECTION_TIMEOUT = 1800

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


def timeout_handler(signum, frame):
    raise TimeoutError("视频处理超时，请检查视频文件或调整超时时间设置")


@app.route("/api/v1/scene-detection/process", methods=["POST"])
def process_scene_detection():
    # 解析请求数据
    try:
        data = request.get_json()
        if not data:
            logger.error("请求体不能为空")
            return jsonify({"error": "请求体不能为空"}), 400

        # 验证必需参数
        required_fields = ["input_path", "output_path", "task_id"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            error_msg = f"缺少必需参数: {', '.join(missing_fields)}"
            logger.error(error_msg)
            return jsonify({"error": error_msg}), 400

        # 获取请求参数
        input_path = data["input_path"]  # 视频路径
        output_path = data["output_path"]  # 输出路径
        task_id = data["task_id"]  # 任务ID
        threshold = data.get("threshold", 0.35)  # 场景切换阈值，默认0.35
        visualize = data.get("visualize", False)  # 是否生成预测可视化

        # 验证视频文件是否存在
        if not os.path.exists(input_path):
            logger.error("视频文件不存在", {"input_path": input_path})
            return jsonify({"error": "视频文件不存在"}), 400

        # 验证视频文件格式
        if not allowed_file(input_path):
            logger.error("不支持的视频文件格式", {"input_path": input_path})
            return jsonify({"error": "不支持的视频文件格式"}), 400

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

        # 设置请求超时处理
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(SCENE_DETECTION_TIMEOUT)

        # 获取视频FPS用于时间戳计算
        cap = None
        video_clip = None
        try:
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                raise ValueError("无法打开视频文件")
            fps = cap.get(cv2.CAP_PROP_FPS)

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

            # 加载视频文件
            logger.info("正在切分场景...")
            video_clip = VideoFileClip(input_path)

            # 格式化场景信息，添加帧号和时间戳
            formatted_scenes = []
            for i, (start, end) in enumerate(scenes):
                start_time = start / video_clip.fps
                end_time = end / video_clip.fps
                segment_clip = video_clip.subclipped(start_time, end_time)

                # 为每个视频片段生成唯一文件名，输出到指定目录
                output_segment_path = f"{output_path}/segment_{i + 1}.mp4"
                logger.info(
                    f"正在导出场景 {i + 1}/{len(scenes)}",
                    {
                        "start_time": format_time(start, video_clip.fps),
                        "end_time": format_time(end, video_clip.fps),
                    },
                )

                # 输出每个视频片段
                segment_clip.write_videofile(
                    output_segment_path, codec="libx264", fps=video_clip.fps
                )
                segment_clip.close()

                formatted_scenes.append(
                    {
                        "start_frame": int(start),
                        "end_frame": int(end),
                        "start_time": format_time(start, fps),
                        "end_time": format_time(end, fps),
                    }
                )

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
            # 确保资源正确释放
            if cap is not None:
                cap.release()
            if video_clip is not None:
                video_clip.close()

    except TimeoutError as e:
        logger.error("处理超时", {"task_id": task_id, "error": str(e)})
        return jsonify({"error": str(e)}), 408
    except Exception as e:
        print(f"\n错误：处理过程中发生异常: {str(e)}")
        # 处理过程中的错误
        error_msg = str(e)
        logger.error("处理过程中发生异常", {"task_id": task_id, "error": error_msg})
        return jsonify({"error": error_msg}), 500
    finally:
        # 确保取消超时设置
        signal.alarm(0)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
