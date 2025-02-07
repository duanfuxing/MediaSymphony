# TransNet V2: 镜头边界检测神经网络

本仓库包含了论文 [TransNet V2: 用于快速镜头转场检测的高效深度网络架构](https://arxiv.org/abs/2008.04838) 的代码实现。

## 性能对比

我们对其他公开可用的最新镜头边界检测方法进行了重新评估（F1 分数）：

模型 | ClipShots | BBC Planet Earth | RAI
--- | :---: | :---: | :---:
TransNet V2 (本仓库) | **77.9** | **96.2** | 93.9
[TransNet](https://arxiv.org/abs/1906.03363) [(github)](https://github.com/soCzech/TransNet) | 73.5 | 92.9 | **94.3**
[Hassanien et al.](https://arxiv.org/abs/1705.03281) [(github)](https://github.com/melgharib/DSBD) | 75.9 | 92.6 | 93.9
[Tang et al., ResNet baseline](https://arxiv.org/abs/1808.04234) [(github)](https://github.com/Tangshitao/ClipShots_basline) | 76.1 | 89.3 | 92.8

## 环境要求

- Python 3.6+
- NVIDIA GPU (推荐)
- Docker (可选，推荐使用)
- FFmpeg (如需直接处理视频文件)

## 快速开始

### Docker 部署（推荐）

#### 自动化部署

我们提供了自动化部署脚本，可以自动配置用户权限并构建镜像：

```bash
# 赋予脚本执行权限
chmod +x start.sh

# 运行安装脚本
./start.sh
```

脚本会自动：
1. 创建必要的目录结构
2. 使用当前用户的 UID 和 GID 构建 Docker 镜像
3. 设置正确的目录权限

#### 手动部署

如果您想手动部署，我们也提供了预构建的 Docker 镜像：

```bash
# 拉取镜像
docker pull catchoco/transnetv2:latest

# 运行容器
docker run -d \
  --gpus all \
  -p 5000:5000 \
  -v /path/to/videos:/app/videos \
  catchoco/transnetv2:latest
```

### 本地安装

1. 安装依赖：
```bash
pip install tensorflow==2.1

# 如需处理视频文件
apt-get install ffmpeg
pip install ffmpeg-python pillow
```

2. 克隆仓库：
```bash
git clone https://github.com/soCzech/TransNetV2.git
cd TransNetV2

# 下载模型权重
git lfs pull
```

## 使用方法

### HTTP API

启动容器后，可以通过 HTTP API 进行视频场景检测：

```bash
# 上传视频并进行场景检测
curl -X POST \
  -F "video=@/path/to/video.mp4" \
  http://localhost:5000/detect_scenes
```

返回结果示例：
```json
{
  "status": "success",
  "scenes": [
    {"start": 0, "end": 120},
    {"start": 121, "end": 350}
  ],
  "output_dir": "videos/outputs/video_name"
}
```

### 命令行工具

您可以使用 `scene_detection.py` 脚本直接处理视频：

```bash
python scene_detection.py \
  --video /path/to/video.mp4 \
  --output /path/to/output/dir \
  --batch-size 32
```

### PyTorch 版本

如果您需要 PyTorch 版本，请查看 [_inference-pytorch_ 文件夹](https://github.com/soCzech/TransNetV2/tree/master/inference-pytorch) 及其说明文档。

##  复现研究

> 注意：训练数据集的大小为数十 GB，导出后可达数百 GB。
>
> **如果您只需要使用模型进行预测，建议使用上述 Docker 部署或命令行工具。**

要复现我们的研究工作，需要按以下步骤进行（在 [_training_ 文件夹](https://github.com/soCzech/TransNetV2/tree/master/training) 中）：

1. 下载数据集：
   - RAI 和 BBC Planet Earth 测试数据集 [(链接)](https://aimagelab.ing.unimore.it/imagelab/researchActivity.asp?idActivity=19)
   - ClipShots 训练/测试数据集 [(链接)](https://github.com/Tangshitao/ClipShots)
   - IACC.3 数据集（可选）

2. 数据准备：
   - 运行 `consolidate_datasets.py` 统一数据集格式
   - 从 ClipShotsTrain 分出验证数据集
   - 运行 `create_dataset.py` 创建数据集

3. 训练与评估：
   - 运行 `training.py ../configs/transnetv2.gin` 训练模型
   - 运行 `evaluate.py /path/to/run_log_dir epoch_no /path/to/test_dataset` 评估模型

## 常见问题

1. **GPU 相关问题**
   - 确保已正确安装 NVIDIA 驱动和 CUDA
   - Docker 部署时确保添加 `--gpus all` 参数

2. **内存不足**
   - 调整 batch size 大小
   - 使用较小的输入视频分辨率

3. **模型权重下载**
   - 确保已安装 git-lfs
   - 运行 `git lfs pull` 下载权重文件

## 引用

如果您觉得本工作有用，请引用我们的论文 ;)

- 本论文：[TransNet V2: 用于快速镜头转场检测的高效深度网络架构](https://arxiv.org/abs/2008.04838)
    ```
    @article{soucek2020transnetv2,
        title={TransNet V2: An effective deep network architecture for fast shot transition detection},
        author={Sou{\v{c}}ek, Tom{\a{s}} and Loko{\v{c}}, Jakub},
        year={2020},
        journal={arXiv preprint arXiv:2008.04838},
    }
    ```

- 旧版本的 ACM Multimedia 论文：[视频中已知项搜索的有效框架](https://dl.acm.org/doi/abs/10.1145/3343031.3351046)

- 旧版本论文：[TransNet: 用于快速检测常见镜头转场的深度网络](https://arxiv.org/abs/1906.03363)
