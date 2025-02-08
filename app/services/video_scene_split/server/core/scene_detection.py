import tensorflow as tf
import numpy as np
import cv2
import argparse
import os
from tqdm import tqdm


# 加载模型
def load_model():
    gpus = tf.config.experimental.list_physical_devices("GPU")
    if gpus:
        try:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
        except RuntimeError as e:
            print(e)
    model = tf.saved_model.load("/app/server/models/transnetv2-weights/")
    return model


# 生成器函数，分批yield视频帧
def get_video_frames_generator(video_path, batch_size=32):
    cap = cv2.VideoCapture(video_path)
    batch_frames = []
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            if batch_frames:  # 处理最后剩余的帧
                yield np.array(batch_frames)
            break
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        batch_frames.append(frame_rgb)
        # 确保每次读取 3 的倍数帧
        if len(batch_frames) == 3:
            yield np.array(batch_frames)
            batch_frames = []
    cap.release()


# 处理视频并按场景切分
def process_video(video_path, output_dir, batch_size=32):
    os.makedirs(output_dir, exist_ok=True)
    # 获取视频信息
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    print(f"视频信息: {width}x{height} @ {fps}fps, 总帧数: {total_frames}")
    # 加载模型
    model = load_model()
    # 分批处理帧并收集预测结果
    all_predictions = []
    frames_buffer = []  # 保存所有帧用于后续切分
    print("正在处理视频帧...")
    for batch_frames in tqdm(
        get_video_frames_generator(video_path, batch_size),
        total=(total_frames + batch_size - 1) // batch_size,
    ):
        batch_frames_5d = np.expand_dims(batch_frames, axis=-1)  # 加入时间维度
        batch_frames_5d = np.repeat(
            batch_frames_5d, 3, axis=-1
        )  # 重复帧数据，确保 depth 是 3 的倍数
        predictions = model.signatures["serving_default"](
            tf.constant(batch_frames_5d.astype(np.float32))
        )
        single_frame_predictions = predictions["cls"][:, 0].numpy()
        all_predictions.extend(single_frame_predictions)
        frames_buffer.extend(batch_frames)
    # 获取场景转换点
    threshold = 0.5
    scene_transitions = [0]  # 添加视频开始点
    print("检测场景转换点...")
    for i in range(1, len(all_predictions)):
        if all_predictions[i] > threshold and all_predictions[i - 1] <= threshold:
            scene_transitions.append(i)
    scene_transitions.append(len(frames_buffer))  # 添加视频结束点
    # 保存每个场景
    print(f"开始保存{len(scene_transitions) - 1}个场景...")
    for i in range(len(scene_transitions) - 1):
        start = scene_transitions[i]
        end = scene_transitions[i + 1]
        # 创建视频写入器
        output_path = os.path.join(
            output_dir, f"scene_{i:04d}_{start:06d}_{end:06d}.mp4"
        )
        out = cv2.VideoWriter(
            output_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )
        # 写入场景帧
        for frame in frames_buffer[start:end]:
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            out.write(frame_bgr)
        out.release()
        print(f"保存场景 {i}: {output_path} (帧 {start} - {end})")


def main():
    parser = argparse.ArgumentParser(description="视频场景切分工具")
    parser.add_argument("--video", required=True, help="输入视频路径")
    parser.add_argument("--output", required=True, help="输出目录路径")
    parser.add_argument("--batch-size", type=int, default=32, help="批处理大小")
    args = parser.parse_args()
    try:
        process_video(args.video, args.output, args.batch_size)
        print("处理完成！")
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        raise


if __name__ == "__main__":
    main()
