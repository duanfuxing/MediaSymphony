import cv2
import numpy as np
from moviepy import VideoFileClip
from tqdm import tqdm

def calculate_sharpness(frame):
    """使用拉普拉斯算子计算图像清晰度"""
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return laplacian_var

def find_best_cover(
    video_path,
    saturation_thresh=0.1,
    sharpness_thresh=80, 
    max_frames=500,
    dual_condition=True
):
    """
    查找满足条件的封面帧
    :param video_path: 视频路径
    :param saturation_thresh: 饱和度阈值 (0-1)
    :param sharpness_thresh: 清晰度阈值（拉普拉斯方差）
    :param max_frames: 最大检查帧数
    :param dual_condition: True=需同时满足两个条件，False=任一条件即可
    :return: (最佳帧, 是否找到理想帧)
    """
    clip = VideoFileClip(video_path)
    best_frame = None
    best_score = -np.inf
    frame_count = 0

    try:
        for frame in tqdm(clip.iter_frames(), total=min(max_frames, int(clip.fps * clip.duration))):
            # 转换为HSV计算饱和度
            hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
            saturation = hsv[:, :, 1].mean() / 255.0
            
            # 计算清晰度
            sharpness = calculate_sharpness(frame)
            
            # 判断条件
            sat_ok = saturation > saturation_thresh
            sharp_ok = sharpness > sharpness_thresh
            
            # 根据条件模式判断
            if (dual_condition and sat_ok and sharp_ok) or \
               (not dual_condition and (sat_ok or sharp_ok)):
                best_frame = frame
                return best_frame, True

            # 记录最佳候选帧
            current_score = saturation + (sharpness / 1000)
            if current_score > best_score:
                best_score = current_score
                best_frame = frame

            frame_count += 1
            if frame_count >= max_frames:
                break

    finally:
        clip.close()

    # 如果未找到理想帧，返回最佳候选
    return best_frame, False

def extract_video_cover(video_path, output_path):
    try:
        target_frame, _ = find_best_cover(video_path)
        if target_frame is not None:
            Image.fromarray(target_frame).save(output_path)
            logger.info(f"封面已保存至 {output_path}")
            return output_path
        return None
    except Exception as e:
        logger.error(f"提取视频封面失败: {str(e)}")
        return None