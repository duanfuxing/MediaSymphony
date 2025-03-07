import cv2
import numpy as np
import os
from PIL import Image
from typing import Tuple, Optional
from moviepy import VideoFileClip
from tqdm import tqdm
from dataclasses import dataclass
from utils.logger import Logger


# 配置日志记录器
logger = Logger("video-frame")

class VideoFrameError(Exception):
    """视频帧处理相关的自定义异常"""
    pass

def calculate_sharpness(frame: np.ndarray) -> float:
    """使用拉普拉斯算子计算图像清晰度
    
    Args:
        frame (np.ndarray): 输入图像帧
        
    Returns:
        float: 清晰度得分
        
    Raises:
        VideoFrameError: 图像处理失败时抛出
    """
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return laplacian_var
    except Exception as e:
        raise VideoFrameError(f"计算图像清晰度失败: {str(e)}")

def calculate_frame_score(frame: np.ndarray, weights: dict = None) -> Tuple[float, float, float]:
    """计算帧的综合得分
    
    Args:
        frame (np.ndarray): 输入图像帧
        weights (dict, optional): 各指标的权重配置
        
    Returns:
        Tuple[float, float, float]: (饱和度, 清晰度, 综合得分)
    """
    if weights is None:
        weights = {"saturation": 1.0, "sharpness": 1.0}
        
    try:
        # 计算饱和度
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        saturation = hsv[:, :, 1].mean() / 255.0
        
        # 计算清晰度
        sharpness = calculate_sharpness(frame) / 1000  # 归一化处理
        
        # 计算加权得分
        score = (
            saturation * weights["saturation"] +
            sharpness * weights["sharpness"]
        ) / sum(weights.values())
        
        return saturation, sharpness, score
    except Exception as e:
        raise VideoFrameError(f"计算帧得分失败: {str(e)}")

def find_best_cover(
    video_path: str,
    saturation_thresh: float = 0.1,
    sharpness_thresh: float = 80.0,
    max_frames: int = 500,
    dual_condition: bool = True,
    frame_weights: dict = None
) -> Tuple[Optional[np.ndarray], bool]:
    """查找满足条件的最佳封面帧
    
    Args:
        video_path (str): 视频路径
        saturation_thresh (float): 饱和度阈值 (0-1)
        sharpness_thresh (float): 清晰度阈值
        max_frames (int): 最大检查帧数
        dual_condition (bool): True=需同时满足两个条件，False=任一条件即可
        frame_weights (dict, optional): 帧评分的权重配置
        
    Returns:
        Tuple[Optional[np.ndarray], bool]: (最佳帧, 是否找到理想帧)
        
    Raises:
        VideoFrameError: 视频处理失败时抛出
    """
    if not video_path or not isinstance(video_path, str):
        raise VideoFrameError("无效的视频路径")
        
    clip = None
    try:
        clip = VideoFileClip(video_path)
        if not clip.reader:
            raise VideoFrameError("无法读取视频文件")
            
        best_frame = None
        best_score = -np.inf
        frame_count = 0
        total_frames = min(max_frames, int(clip.fps * clip.duration))

        for frame in tqdm(clip.iter_frames(), total=total_frames, desc="分析视频帧"):
            try:
                saturation, sharpness, current_score = calculate_frame_score(frame, frame_weights)
                
                # 判断条件
                sat_ok = saturation > saturation_thresh
                sharp_ok = (sharpness * 1000) > sharpness_thresh  # 还原原始比例
                
                # 根据条件模式判断
                if (dual_condition and sat_ok and sharp_ok) or \
                   (not dual_condition and (sat_ok or sharp_ok)):
                    return frame, True

                # 更新最佳候选帧
                if current_score > best_score:
                    best_score = current_score
                    best_frame = frame

                frame_count += 1
                if frame_count >= max_frames:
                    break
                    
            except VideoFrameError as e:
                logger.warning(f"处理第{frame_count}帧时出现警告: {str(e)}")
                continue

        return best_frame, False

    except Exception as e:
        raise VideoFrameError(f"查找最佳封面帧失败: {str(e)}")
    finally:
        if clip is not None:
            try:
                clip.close()
            except Exception as e:
                logger.error(f"关闭视频文件失败: {str(e)}")

@dataclass
class VideoMetadata:
    """视频元数据类"""
    duration: float = 0.0  # 视频时长(秒)
    width: int = 0      # 视频宽度
    height: int = 0     # 视频高度
    aspect_ratio: float = 0.0  # 宽高比(数值)
    aspect_ratio_text: str = ""  # 宽高比(文本形式，如16:9)
    file_size: int = 0      # 文件大小(字节)
    fps: float = 0.0        # 帧率
    bitrate: float = 0.0    # 码率(bytes/second)
    cover_path: Optional[str] = None  # 封面图片路径
    is_ideal_cover: bool = False      # 是否为理想封面

def calculate_aspect_ratio_text(width: int, height: int) -> str:
    """计算宽高比的文本表示形式
    
    Args:
        width (int): 宽度
        height (int): 高度
        
    Returns:
        str: 宽高比的文本表示，如"16:9"
    """
    if width <= 0 or height <= 0:
        return ""
        
    # 计算最大公约数
    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a
    
    divisor = gcd(width, height)
    simplified_width = width // divisor
    simplified_height = height // divisor
    
    # 检查是否为常见宽高比
    common_ratios = {
        (16, 9): "16:9",
        (4, 3): "4:3",
        (21, 9): "21:9",
        (1, 1): "1:1",
        (3, 2): "3:2",
        (9, 16): "9:16",  # 竖屏
        (2, 3): "2:3",    # 竖屏
    }
    
    ratio = (simplified_width, simplified_height)
    if ratio in common_ratios:
        return common_ratios[ratio]
    
    # 如果不是常见比例，但比例值很大，尝试近似到常见比例
    if simplified_width > 20 or simplified_height > 20:
        # 计算浮点数比例
        float_ratio = width / height
        
        # 常见比例的浮点数值
        common_float_ratios = {
            16/9: "16:9",
            4/3: "4:3", 
            21/9: "21:9",
            1/1: "1:1",
            3/2: "3:2",
            9/16: "9:16",
            2/3: "2:3"
        }
        
        # 查找最接近的常见比例
        closest_ratio = min(common_float_ratios.keys(), key=lambda x: abs(x - float_ratio))
        if abs(closest_ratio - float_ratio) < 0.05:  # 5%误差内认为是该比例
            return common_float_ratios[closest_ratio]
    
    # 返回简化后的比例
    return f"{simplified_width}:{simplified_height}"

def get_video_metadata(video_path: str, cover_path: Optional[str] = None, is_ideal: bool = False) -> VideoMetadata:
    """获取视频元数据
    
    Args:
        video_path (str): 视频文件路径
        cover_path (Optional[str]): 封面图片路径
        is_ideal (bool): 是否为理想封面
        
    Returns:
        VideoMetadata: 视频元数据对象，失败时返回包含默认值的对象
    """
    metadata = VideoMetadata(cover_path=cover_path, is_ideal_cover=is_ideal)
    
    if not os.path.exists(video_path):
        logger.error(f"视频文件不存在: {video_path}")
        return metadata
        
    try:
        clip = VideoFileClip(video_path)
        file_size = os.path.getsize(video_path)
        
        # 防止除零错误
        duration = max(clip.duration, 0.001)
        
        width = clip.w
        height = clip.h
        
        metadata.duration = duration
        metadata.width = width
        metadata.height = height
        metadata.aspect_ratio = width / max(height, 1)  # 防止除零
        metadata.aspect_ratio_text = calculate_aspect_ratio_text(width, height)
        metadata.file_size = file_size
        metadata.fps = clip.fps
        metadata.bitrate = file_size / duration
        
        clip.close()
    except Exception as e:
        logger.error(f"获取视频元数据失败: {str(e)}")
    
    return metadata

def save_frame_as_cover(frame: np.ndarray, output_path: str) -> bool:
    """将帧保存为封面图片
    
    Args:
        frame (np.ndarray): 视频帧
        output_path (str): 输出图片路径
        
    Returns:
        bool: 保存成功返回True，否则返回False
    """
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        Image.fromarray(frame).save(output_path)
        logger.info(f"已保存封面至 {output_path}")
        return True
    except Exception as e:
        logger.error(f"保存封面图片失败: {str(e)}")
        return False

def get_first_frame(video_path: str) -> Optional[np.ndarray]:
    """获取视频的第一帧
    
    Args:
        video_path (str): 视频文件路径
        
    Returns:
        Optional[np.ndarray]: 第一帧，失败时返回None
    """
    try:
        if not os.path.exists(video_path):
            logger.error(f"视频文件不存在: {video_path}")
            return None
            
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"无法打开视频: {video_path}")
            return None
            
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            logger.error(f"无法读取视频第一帧: {video_path}")
            return None
            
        # 转换BGR到RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame_rgb
    except Exception as e:
        logger.error(f"获取视频第一帧失败: {str(e)}")
        return None

def extract_video_cover_with_metadata(video_path: str, output_path: str) -> VideoMetadata:
    """提取视频封面并返回视频元数据
    
    Args:
        video_path (str): 视频文件路径
        output_path (str): 输出图片路径
        
    Returns:
        VideoMetadata: 包含视频元数据和封面信息的对象，即使部分操作失败也会返回尽可能多的信息
    """
    # 初始化默认元数据
    metadata = VideoMetadata()
    is_ideal = False
    cover_saved = False
    
    if not os.path.exists(video_path):
        logger.error(f"视频文件不存在: {video_path}")
        return metadata
    
    # 尝试获取最佳封面帧
    try:
        target_frame, is_ideal = find_best_cover(video_path)
        if target_frame is not None:
            if save_frame_as_cover(target_frame, output_path):
                cover_saved = True
            else:
                logger.warning("保存封面失败")
                raise VideoFrameError("保存封面失败")
        else:
            logger.warning("未能找到合适的封面帧")
            raise VideoFrameError("未能找到合适的封面帧")
    except VideoFrameError as e:
        logger.warning(f"查找最佳封面失败: {str(e)}，尝试使用第一帧作为封面")
        # 尝试使用第一帧作为封面
        first_frame = get_first_frame(video_path)
        if first_frame is not None:
            if save_frame_as_cover(first_frame, output_path):
                cover_saved = True
                logger.info(f"已使用第一帧作为封面保存至 {output_path}")
            else:
                logger.warning("保存第一帧作为封面失败")
        else:
            logger.error("无法获取视频第一帧")
    except Exception as e:
        logger.error(f"提取视频封面时发生未知错误: {str(e)}")
    
    # 无论封面是否成功提取，都尝试获取视频元数据
    try:
        # 只有成功保存了封面才传递封面路径
        cover_path = output_path if cover_saved else None
        metadata = get_video_metadata(video_path, cover_path, is_ideal)
    except Exception as e:
        logger.error(f"获取视频元数据失败: {str(e)}")
    
    return metadata

# if __name__ == "__main__":
#     video_path = "no-second.mp4"
#     output_path = "/home/eleven/cover.jpg"
#     metadata = extract_video_cover_with_metadata(video_path, output_path)
    
#     print(f"视频信息:")
#     print(f"时长: {metadata.duration:.2f}秒")
#     print(f"分辨率: {metadata.width}x{metadata.height}")
#     print(f"宽高比: {metadata.aspect_ratio:.2f} ({metadata.aspect_ratio_text})")
#     print(f"文件大小: {metadata.file_size/1024/1024:.2f}MB")
#     print(f"帧率: {metadata.fps:.2f}fps")
#     print(f"码率: {metadata.bitrate/1024:.2f}KB/s")
#     print(f"封面路径: {metadata.cover_path if metadata.cover_path else '未保存封面'}")
#     print(f"是否理想封面: {metadata.is_ideal_cover}")