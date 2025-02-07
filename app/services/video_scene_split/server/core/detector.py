import os
import numpy as np
import tensorflow as tf


class SceneDetector:
    def __init__(self, model_dir=None):
        if model_dir is None:
            model_dir = os.path.join(
                os.path.dirname(__file__), "../models/transnetv2-weights/"
            )
            if not os.path.isdir(model_dir):
                raise FileNotFoundError(
                    f"[TransNetV2] ERROR: {model_dir} is not a directory."
                )
            else:
                print(f"[TransNetV2] Using weights from {model_dir}.")

        # GPU配置
        self._setup_gpu()

        # 模型配置
        self._input_size = (27, 48, 3)
        try:
            self._model = tf.saved_model.load(model_dir)
        except OSError as exc:
            raise IOError(f"[TransNetV2] 模型文件损坏或丢失: {model_dir}")

    def _setup_gpu(self):
        """配置GPU设置"""
        gpus = tf.config.experimental.list_physical_devices("GPU")
        if gpus:
            try:
                gpu = gpus[0]
                tf.config.experimental.set_memory_growth(gpu, True)
                tf.config.experimental.set_virtual_device_configuration(
                    gpu,
                    [
                        tf.config.experimental.VirtualDeviceConfiguration(
                            memory_limit=4096
                        )
                    ],
                )
            except RuntimeError as e:
                print(f"GPU配置错误: {e}")

    def predict_raw(self, frames: np.ndarray):
        """对原始帧进行预测"""
        assert (
            len(frames.shape) == 5 and frames.shape[2:] == self._input_size
        ), "[TransNetV2] 输入形状必须为 [batch, frames, height, width, 3]."
        frames = tf.cast(frames, tf.float32)

        logits, dict_ = self._model(frames)
        single_frame_pred = tf.sigmoid(logits)
        all_frames_pred = tf.sigmoid(dict_["many_hot"])

        return single_frame_pred, all_frames_pred

    def predict_frames(self, frames: np.ndarray):
        """预测视频帧的场景转换"""
        assert (
            len(frames.shape) == 4 and frames.shape[1:] == self._input_size
        ), "[TransNetV2] 输入形状必须为 [frames, height, width, 3]."

        def input_iterator():
            no_padded_frames_start = 25
            no_padded_frames_end = (
                25 + 50 - (len(frames) % 50 if len(frames) % 50 != 0 else 50)
            )

            start_frame = np.expand_dims(frames[0], 0)
            end_frame = np.expand_dims(frames[-1], 0)
            padded_inputs = np.concatenate(
                [start_frame] * no_padded_frames_start
                + [frames]
                + [end_frame] * no_padded_frames_end,
                0,
            )

            ptr = 0
            while ptr + 100 <= len(padded_inputs):
                out = padded_inputs[ptr : ptr + 100]
                ptr += 50
                yield out[np.newaxis]

        predictions = []
        for inp in input_iterator():
            single_frame_pred, all_frames_pred = self.predict_raw(inp)
            predictions.append(
                (
                    single_frame_pred.numpy()[0, 25:75, 0],
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

        single_frame_pred = np.concatenate([single_ for single_, all_ in predictions])
        all_frames_pred = np.concatenate([all_ for single_, all_ in predictions])

        return single_frame_pred[: len(frames)], all_frames_pred[: len(frames)]

    def predict_video(self, video_fn: str):
        """预测视频文件的场景转换"""
        try:
            import ffmpeg
        except ModuleNotFoundError:
            raise ModuleNotFoundError("需要安装ffmpeg-python来提取视频帧")

        print(f"[TransNetV2] 正在从{video_fn}提取帧")
        video_stream, err = (
            ffmpeg.input(video_fn)
            .output("pipe:", format="rawvideo", pix_fmt="rgb24", s="48x27")
            .run(capture_stdout=True, capture_stderr=True)
        )

        video = np.frombuffer(video_stream, np.uint8).reshape([-1, 27, 48, 3])
        return (video, *self.predict_frames(video))

    @staticmethod
    def predictions_to_scenes(predictions: np.ndarray, threshold: float = 0.5):
        """将预测结果转换为场景列表"""
        predictions = (predictions > threshold).astype(np.uint8)

        scenes = []
        t, t_prev, start = -1, 0, 0
        for i, t in enumerate(predictions):
            if t_prev == 1 and t == 0:
                start = i
            if t_prev == 0 and t == 1 and i != 0:
                scenes.append([start, i])
            t_prev = t
        if t == 0:
            scenes.append([start, i])

        if len(scenes) == 0:
            return np.array([[0, len(predictions) - 1]], dtype=np.int32)

        return np.array(scenes, dtype=np.int32)
