import os
import sys
import cv2
import argparse
import tensorflow as tf
from tqdm import tqdm
from moviepy import VideoFileClip
import numpy as np
import tensorflow as tf


class SceneDetector:
    """场景检测器类

    该类用于视频场景切分，能够检测视频中的场景转换点，并支持场景预测的可视化。
    基于TransNetV2模型实现，支持GPU加速。
    """

    def __init__(self, logger=None):
        """初始化场景检测器

        Args:
            logger: 日志记录器实例
            model_dir (str, optional): 模型权重文件目录路径。如果为None，将使用默认路径。
        """
        self.logger = logger

        # 模型目录
        model_dir = "/app/server/models/transnetv2-weights"

        # GPU配置初始化
        try:
            gpus = tf.config.experimental.list_physical_devices("GPU")
            if gpus:
                # 为所有GPU设置内存动态增长
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                if self.logger:
                    self.logger.info(f"已启用 {len(gpus)} 个GPU的动态内存分配")
        except RuntimeError as e:
            if self.logger:
                self.logger.warning(f"[警告] GPU内存配置失败: {e}")
                self.logger.info("将使用CPU进行处理")
        except Exception as e:
            if self.logger:
                self.logger.error(f"[错误] GPU初始化失败: {e}")
                self.logger.info("将使用CPU进行处理")

        # 设置输入尺寸并加载模型
        self._input_size = (27, 48, 3)  # 模型要求的输入尺寸：高度27，宽度48，3通道

        # 加载模型
        try:
            self._model = tf.saved_model.load(model_dir)
        except OSError as exc:
            raise IOError(
                f"[TransNetV2] {model_dir} 中的文件已损坏或丢失。"
                f"请手动重新下载并重试。更多信息请参考："
                f"https://github.com/soCzech/TransNetV2/issues/1#issuecomment-647357796"
            ) from exc

    def predict_raw(self, frames: np.ndarray):
        """对输入的帧批次进行原始预测

        Args:
            frames (np.ndarray): 输入帧数组，形状为[batch, frames, height, width, 3]

        Returns:
            tuple: (single_frame_pred, all_frames_pred) 单帧预测和所有帧预测的结果
        """
        assert (
            len(frames.shape) == 5 and frames.shape[2:] == self._input_size
        ), "[TransNetV2] 输入形状必须为 [batch, frames, height, width, 3]。"
        frames = tf.cast(frames, tf.float32)

        # 使用模型进行预测
        logits, dict_ = self._model(frames)
        single_frame_pred = tf.sigmoid(logits)  # 单帧预测结果
        all_frames_pred = tf.sigmoid(dict_["many_hot"])  # 多帧预测结果

        return single_frame_pred, all_frames_pred

    def predict_frames(self, frames: np.ndarray):
        """预测视频帧序列中的场景转换

        Args:
            frames (np.ndarray): 输入帧序列，形状为[frames, height, width, 3]

        Returns:
            tuple: (single_frame_predictions, all_frames_predictions) 返回单帧和多帧的预测结果
        """
        assert (
            len(frames.shape) == 4 and frames.shape[1:] == self._input_size
        ), "[TransNetV2] 输入形状必须为 [frames, height, width, 3]。"

        def input_iterator():
            # 返回大小为100的窗口，其中第一个/最后一个25帧来自前一个/下一个批次
            # 视频的第一个和最后一个窗口必须由视频的第一帧和最后一帧的副本进行填充
            no_padded_frames_start = 25
            no_padded_frames_end = (
                25 + 50 - (len(frames) % 50 if len(frames) % 50 != 0 else 50)
            )  # 25 - 74

            # 创建帧序列的填充
            start_frame = np.expand_dims(frames[0], 0)  # 使用第一帧进行起始填充
            end_frame = np.expand_dims(frames[-1], 0)  # 使用最后一帧进行结束填充
            padded_inputs = np.concatenate(
                [start_frame] * no_padded_frames_start
                + [frames]
                + [end_frame] * no_padded_frames_end,
                0,
            )

            # 以50帧为步长生成100帧的滑动窗口
            ptr = 0
            while ptr + 100 <= len(padded_inputs):
                out = padded_inputs[ptr : ptr + 100]
                ptr += 50
                yield out[np.newaxis]

        predictions = []

        # 对每个批次进行预测
        for inp in input_iterator():
            single_frame_pred, all_frames_pred = self.predict_raw(inp)
            predictions.append(
                (
                    single_frame_pred.numpy()[0, 25:75, 0],  # 提取中间50帧的预测结果
                    all_frames_pred.numpy()[0, 25:75, 0],
                )
            )

            print(
                "\r[TransNetV2] 正在处理视频帧 {}/{}".format(
                    min(len(predictions) * 50, len(frames)), len(frames)
                ),
                end="",
            )
        print("")

        # 合并所有预测结果
        single_frame_pred = np.concatenate([single_ for single_, all_ in predictions])
        all_frames_pred = np.concatenate([all_ for single_, all_ in predictions])

        return (
            single_frame_pred[: len(frames)],
            all_frames_pred[: len(frames)],
        )

    def predict_video(self, video_fn: str):
        """预测视频文件中的场景转换

        Args:
            video_fn (str): 视频文件路径

        Returns:
            tuple: (video_frames, single_frame_predictions, all_frames_predictions)
        """
        try:
            import ffmpeg
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "缺少ffmpeg，执行 `pip install ffmpeg-python` 安装 Python 包装器。"
            )

        print(f"[TransNetV2] 正在从 {video_fn} 提取帧")
        # 使用ffmpeg提取视频帧
        video_stream, err = (
            ffmpeg.input(video_fn)
            .output("pipe:", format="rawvideo", pix_fmt="rgb24", s="48x27")
            .run(capture_stdout=True, capture_stderr=True)
        )

        # 将视频流转换为numpy数组
        video = np.frombuffer(video_stream, np.uint8).reshape([-1, 27, 48, 3])
        return (video, *self.predict_frames(video))

    @staticmethod
    def predictions_to_scenes(predictions: np.ndarray, threshold: float = 0.5):
        """将预测结果转换为场景边界

        Args:
            predictions (np.ndarray): 预测结果数组
            threshold (float, optional): 判断场景转换的阈值。默认为0.5

        Returns:
            np.ndarray: 场景边界数组，每个元素为[start_frame, end_frame]
        """
        # 将预测概率转换为二值结果
        predictions = (predictions > threshold).astype(np.uint8)

        scenes = []
        t, t_prev, start = -1, 0, 0
        # 遍历预测结果，检测场景边界
        for i, t in enumerate(predictions):
            if t_prev == 1 and t == 0:  # 检测到场景结束
                start = i
            if t_prev == 0 and t == 1 and i != 0:  # 检测到新场景开始
                scenes.append([start, i])
            t_prev = t
        if t == 0:  # 处理最后一个场景
            scenes.append([start, i])

        # 修复所有预测都为1的情况
        if len(scenes) == 0:
            return np.array([[0, len(predictions) - 1]], dtype=np.int32)

        return np.array(scenes, dtype=np.int32)

    @staticmethod
    def visualize_predictions(frames: np.ndarray, predictions):
        """可视化预测结果

        Args:
            frames (np.ndarray): 视频帧数组
            predictions: 预测结果，可以是单个预测数组或多个预测数组的列表

        Returns:
            PIL.Image: 可视化结果图像
        """
        from PIL import Image, ImageDraw

        if isinstance(predictions, np.ndarray):
            predictions = [predictions]

        ih, iw, ic = frames.shape[1:]  # 获取帧的高度、宽度和通道数
        width = 25  # 设置显示宽度

        # 填充帧，使视频长度能被宽度整除
        # 同时在宽度方向上填充len(predictions)个像素以显示预测结果
        pad_with = width - len(frames) % width if len(frames) % width != 0 else 0
        frames = np.pad(frames, [(0, pad_with), (0, 1), (0, len(predictions)), (0, 0)])

        # 对预测结果进行填充
        predictions = [np.pad(x, (0, pad_with)) for x in predictions]
        height = len(frames) // width

        # 重塑帧数组以便可视化
        img = frames.reshape([height, width, ih + 1, iw + len(predictions), ic])
        img = np.concatenate(
            np.split(np.concatenate(np.split(img, height), axis=2)[0], width), axis=2
        )[0, :-1]

        # 创建图像对象
        img = Image.fromarray(img)
        draw = ImageDraw.Draw(img)

        # 遍历所有帧，绘制预测结果
        for i, pred in enumerate(zip(*predictions)):
            x, y = i % width, i // width
            x, y = x * (iw + len(predictions)) + iw, y * (ih + 1) + ih - 1

            # 为每一帧可视化多个预测结果
            for j, p in enumerate(pred):
                color = [0, 0, 0]
                color[(j + 1) % 3] = 255  # 为不同预测结果使用不同颜色

                value = round(p * (ih - 1))  # 计算预测值的显示高度
                if value != 0:
                    draw.line((x + j, y, x + j, y - value), fill=tuple(color), width=1)
        return img
