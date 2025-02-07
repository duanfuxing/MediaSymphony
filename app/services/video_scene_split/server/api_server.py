from flask import Flask, request, jsonify
import os
from scene_detection import SceneDetector
from werkzeug.utils import secure_filename

app = Flask(__name__)
detector = SceneDetector()
UPLOAD_FOLDER = "videos/uploads"
OUTPUT_FOLDER = "videos/outputs"
ALLOWED_EXTENSIONS = {"mp4", "avi", "mov"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/detect_scenes", methods=["POST"])
def detect_scenes():
    if "video" not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    file = request.files["video"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file"}), 400
    # 保存上传的视频
    filename = secure_filename(file.filename)
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(input_path)
    # 创建输出目录
    output_dir = os.path.join(OUTPUT_FOLDER, filename.rsplit(".", 1)[0])
    os.makedirs(output_dir, exist_ok=True)
    # 处理视频
    try:
        scenes = detector.process_video(input_path, output_dir)
        return jsonify(
            {
                "status": "success",
                "scenes": [
                    {"start": int(start), "end": int(end)} for start, end in scenes
                ],
                "output_dir": output_dir,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    app.run(host="0.0.0.0", port=5000)
