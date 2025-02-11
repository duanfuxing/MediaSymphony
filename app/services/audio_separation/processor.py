from config import settings
from audio_separator.separator import Separator
import os


class AudioSeparatorProcessor:
    def __init__(self):
        self.separator = Separator(
            output_single_stem="Vocals",
            model_file_dir=settings.MODEL_DIR
        )

    def process_audio(self, aduio_path: str, task_id: str, output_path):
        # 判断 output_path 目录是否存在，不存在创建
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        # 实例化 separator 类
        self.separator = Separator(
            output_single_stem="Vocals",
            model_file_dir=settings.MODEL_DIR,
            output_dir=output_path
        )

        self.separator.load_model(model_filename=settings.MODEL_FILENAME)
        # 修改输出文件的命名
        output_names = {
            "Vocals": f"vocals_{task_id}",
            "Instrumental": f"accompaniment_{task_id}"
        }
        return self.separator.separate(aduio_path, output_names)