import tensorflow as tf
import numpy as np
import cv2
import os
from tqdm import tqdm

class SceneDetector:
    def __init__(self, model_path='../models/transnetv2-weights/', threshold=0.5):
        """
        初始化场景检测器
        
        Args:
            model_path (str): 模型权重路径
            threshold (float): 场景切换判定阈值
        """
        self.model_path = model_path
        self.threshold = threshold
        self.model = None
        self._setup_gpu()
        self._load_model()

    def _setup_gpu(self):
        """配置GPU内存增长"""
        gpus = tf.config.experimental.list_physical_devices('GPU')
        if gpus:
            try:
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
            except RuntimeError as e:
                print(f"GPU配置错误: {e}")

    def _load_model(self):
        """加载TensorFlow模型"""
        try:
            self.model = tf.saved_model.load(self.model_path)
        except Exception as e:
            raise RuntimeError(f"模型加载失败: {e}")

    def _get_video_info(self, video_path):
        """
        获取视频基本信息
        
        Returns:
            tuple: (fps, width, height, total_frames)
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")
        
        info = {
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        }
        cap.release()
        return info

    def _frame_generator(self, video_path, batch_size=32):
        """
        生成器函数，分批yield视频帧
        
        Args:
            video_path (str): 视频文件路径
            batch_size (int): 批处理大小
        
        Yields:
            np.ndarray: 批量视频帧
        """
        cap = cv2.VideoCapture(video_path)
        batch_frames = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                if batch_frames:
                    yield np.array(batch_frames)
                break
                
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            batch_frames.append(frame_rgb)
            
            if len(batch_frames) == 3:  # 确保每次读取3的倍数帧
                yield np.array(batch_frames)
                batch_frames = []
                
        cap.release()

    def _get_scene_transitions(self, predictions):
        """
        根据预测结果获取场景转换点
        
        Args:
            predictions (list): 模型预测结果
            
        Returns:
            list: 场景转换帧索引列表
        """
        transitions = [0]  # 添加视频开始点
        for i in range(1, len(predictions)):
            if predictions[i] > self.threshold and predictions[i - 1] <= self.threshold:
                transitions.append(i)
        transitions.append(len(predictions))  # 添加视频结束点
        return transitions

    def _save_scene(self, frames, start, end, output_path, fps, width, height):
        """
        保存单个场景片段
        
        Args:
            frames (list): 帧列表
            start (int): 起始帧索引
            end (int): 结束帧索引
            output_path (str): 输出文件路径
            fps (float): 帧率
            width (int): 视频宽度
            height (int): 视频高度
        """
        out = cv2.VideoWriter(
            output_path,
            cv2.VideoWriter_fourcc(*'mp4v'),
            fps,
            (width, height)
        )
        
        for frame in frames[start:end]:
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            out.write(frame_bgr)
        out.release()

    def process_video(self, video_path, output_dir, batch_size=32):
        """
        检测视频场景并保存
        
        Args:
            video_path (str): 输入视频路径
            output_dir (str): 输出目录路径
            batch_size (int): 批处理大小
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取视频信息
        video_info = self._get_video_info(video_path)
        print(f"视频信息: {video_info['width']}x{video_info['height']} @ {video_info['fps']}fps, "
              f"总帧数: {video_info['total_frames']}")

        # 处理视频帧并收集预测结果
        all_predictions = []
        frames_buffer = []
        print("正在处理视频帧...")
        
        for batch_frames in tqdm(self._frame_generator(video_path, batch_size),
                               total=(video_info['total_frames'] + batch_size - 1) // batch_size):
            # 处理帧
            batch_frames_5d = np.expand_dims(batch_frames, axis=-1)
            batch_frames_5d = np.repeat(batch_frames_5d, 3, axis=-1)
            
            # 获取预测结果
            predictions = self.model.signatures["serving_default"](
                tf.constant(batch_frames_5d.astype(np.float32))
            )
            single_frame_predictions = predictions["cls"][:, 0].numpy()
            
            all_predictions.extend(single_frame_predictions)
            frames_buffer.extend(batch_frames)

        # 获取场景转换点并保存场景
        scene_transitions = self._get_scene_transitions(all_predictions)
        print(f"检测到{len(scene_transitions) - 1}个场景，开始保存...")
        
        for i in range(len(scene_transitions) - 1):
            start = scene_transitions[i]
            end = scene_transitions[i + 1]
            output_path = os.path.join(output_dir, f'scene_{i:04d}_{start:06d}_{end:06d}.mp4')
            
            self._save_scene(
                frames_buffer, start, end, output_path,
                video_info['fps'], video_info['width'], video_info['height']
            )
            print(f"保存场景 {i}: {output_path} (帧 {start} - {end})")