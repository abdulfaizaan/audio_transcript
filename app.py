# app.py
from flask import Flask, request, jsonify, render_template
from google import genai
import os, uuid, base64
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import time

def safe_generate_content(model, prompt, retries=3, delay=5):
    for i in range(retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "503" in str(e) and i < retries - 1:
                print(f"Retrying after 503... ({i+1}/{retries})")
                time.sleep(delay)
            else:
                raise e

load_dotenv()
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static'
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'webm', 'm4a'}
MODEL_NAME = "gemini-2.5-pro"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def audio_to_base64(fp):
    return base64.b64encode(open(fp, "rb").read()).decode()

# Initialize Gen AI client
genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
models = genai_client.models

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    target_language = request.form.get('language', 'Hindi')
    if not file or file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file'}), 400

    ext = file.filename.rsplit('.',1)[1].lower()
    fn = f"{uuid.uuid4().hex}.{ext}"
    fp = os.path.join(app.config['UPLOAD_FOLDER'], fn)
    file.save(fp)

    try:
        audio_b64 = audio_to_base64(fp)

        # Transcribe with Gemini
        resp1 = models.generate_content(
            model=MODEL_NAME,
            contents=(
                "Please transcribe the following English audio (base64):\n\n"
                f"{audio_b64}"
            )
        )
        transcript = resp1.text.strip()

        # Translate
        resp2 = models.generate_content(
            model=MODEL_NAME,
            contents=f"Translate the following English text into {target_language}:\n\n{transcript}"
        )
        translation = resp2.text.strip()

        os.remove(fp)
        return jsonify({'transcript': transcript, 'translated_text': translation})

    except Exception as e:
        return jsonify({'error': f'Gemini error: {e}'}), 500

if __name__ == "__main__":
    app.run(debug=True)
