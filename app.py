import os
import time
import uuid
import threading
import glob
import logging
import io
from flask import Flask, request, send_file, jsonify, render_template_string
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import fitz  # PyMuPDF
from PIL import Image

app = Flask(__name__)

# --- AYARLAR ---
UPLOAD_FOLDER = "uploads"
app.config['MAX_CONTENT_LENGTH'] = None  # Limitsiz
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- LOGLAMA ---
if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
else:
    logging.basicConfig(level=logging.INFO)

# --- GLOBAL DURUM ---
job_status = {}

# --- AGRESİF SIKIŞTIRMA FONKSİYONU ---
def compress_pdf_aggressive(input_path, output_path, job_id):
    try:
        doc = fitz.open(input_path)
        total_pages = len(doc)
        if total_pages == 0: total_pages = 1

        for i, page in enumerate(doc):
            image_list = page.get_images()
            for img_info in image_list:
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    img = Image.open(io.BytesIO(image_bytes))
                    
                    if img.width < 150 or img.height < 150: continue
                        
                    max_width = 1024
                    if img.width > max_width:
                        ratio = max_width / img.width
                        new_height = int(img.height * ratio)
                        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                    
                    buffer = io.BytesIO()
                    if img.mode != "RGB": img = img.convert("RGB")
                    img.save(buffer, format="JPEG", quality=70, optimize=True)
                    doc.update_stream(xref, buffer.getvalue())
                    
                except Exception as e:
                    print(f"Resim hatası: {e}")
                    continue
            
            job_status[job_id]["progress"] = int(((i + 1) / total_pages) * 90)

        job_status[job_id]["stage"] = "saving"
        doc.save(output_path, garbage=4, deflate=True, clean=True)
        doc.close()
        
    except Exception as e:
        raise e

# --- ARKA PLAN GÖREVİ ---
def optimize_pdf_task(input_path, output_path, job_id):
    try:
        job_status[job_id]["stage"] = "processing"
        job_status[job_id]["progress"] = 5
        
        # Sıkıştırma işlemini yap
        compress_pdf_aggressive(input_path, output_path, job_id)
            
        original_size = os.path.getsize(input_path)
        optimized_size = os.path.getsize(output_path)
        
        # GİZLİLİK ADIM 1: Orijinal dosyayı iş biter bitmez sil
        if os.path.exists(input_path):
            os.remove(input_path)
            app.logger.info(f"Orijinal dosya silindi: {input_path}")
        
        job_status[job_id].update({
            "stage": "completed",
            "progress": 100,
            "stats": {
                "original": f"{original_size / 1024:.1f} KB",
                "optimized": f"{optimized_size / 1024:.1f} KB"
            },
            "filename": os.path.basename(output_path)
        })
        
    except Exception as e:
        app.logger.error(f"Optimizasyon Hatası: {e}")
        job_status[job_id]["stage"] = "error"
        job_status[job_id]["message"] = "Dosya işlenirken hata oluştu."
        if os.path.exists(input_path): os.remove(input_path)

# --- HTML TASARIM (FAVICON EKLENDİ) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Güvenli PDF Optimize</title>
    
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📄</text></svg>">
    
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Poppins', sans-serif; background: linear-gradient(135deg, #667eea, #764ba2); min-height: 100vh; display: flex; justify-content: center; align-items: center; color: #fff; }
        .container { background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px); padding: 50px 40px; border-radius: 25px; box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3); text-align: center; width: 95%; max-width: 550px; border: 1px solid rgba(255, 255, 255, 0.2); }
        h1 { font-size: 2.5rem; margin-bottom: 10px; letter-spacing: 1px; }
        .subtitle { font-size: 0.9rem; margin-bottom: 30px; opacity: 0.8; color: #e0e7ff; background: rgba(0,0,0,0.2); padding: 5px 15px; border-radius: 20px; display: inline-block; }
        .btn { padding: 18px 40px; background: linear-gradient(90deg, #ff7eb3, #ff758c); border: none; border-radius: 15px; cursor: pointer; font-weight: 700; color: white; font-size: 1.1rem; display: inline-block; transition: all 0.3s ease; box-shadow: 0 5px 20px rgba(0, 0, 0, 0.2); text-decoration: none; margin-top: 10px; }
        .btn:hover { transform: translateY(-3px) scale(1.02); }
        .secondary-btn { background: rgba(255,255,255,0.2); margin-top: 20px; font-size: 0.9rem; padding: 12px 25px; }
        .progress-container { width: 100%; background-color: rgba(255, 255, 255, 0.2); border-radius: 20px; margin: 20px 0; height: 25px; overflow: hidden; }
        .progress-bar { width: 0%; height: 100%; background: linear-gradient(90deg, #ff7eb3, #ff758c); transition: width 0.4s ease; }
        .stats-box { background: rgba(0,0,0,0.2); padding: 15px; border-radius: 15px; margin-bottom: 25px; text-align: left; }
        .hidden { display: none !important; }
        .file-name { margin-top: 15px; font-weight: 600; }
        .error-box { background: rgba(255, 0, 0, 0.2); color: #ffcccc; padding: 15px; border-radius: 15px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📄 PDF Optimize</h1>
        <div class="subtitle">🔒 Dosyalarınız işlem sonrası otomatik silinir</div>

        <div id="uploadSection">
            <input type="file" id="fileInput" accept="application/pdf" style="display: none;">
            <label for="fileInput" class="btn">📂 PDF Seç</label>
            <div id="selectedFileName" class="file-name"></div>
        </div>

        <div id="processSection" class="hidden">
            <div class="progress-container"><div class="progress-bar" id="progressBar"></div></div>
            <div id="statusText" style="font-weight: 600;">Yükleniyor...</div>
        </div>

        <div id="resultSection" class="hidden">
            <div id="statsBox" class="stats-box"></div>
            <a id="downloadLink" href="#" class="btn">⬇️ İndir ve Sil</a>
            <br>
            <button class="btn secondary-btn" onclick="location.reload()">Yeni Dosya</button>
        </div>

        <div id="errorSection" class="hidden">
            <div id="errorBox" class="error-box"></div>
            <button class="btn secondary-btn" onclick="location.reload()">Tekrar Dene</button>
        </div>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            document.getElementById('selectedFileName').innerText = "Seçilen: " + file.name;
            startUpload(file);
        });

        async function startUpload(file) {
            document.getElementById('uploadSection').classList.add('hidden');
            document.getElementById('processSection').classList.remove('hidden');
            updateProgress(0, "Yükleniyor...");

            const formData = new FormData();
            formData.append('pdf', file);

            try {
                const res = await fetch('/upload', { method: 'POST', body: formData });
                const contentType = res.headers.get("content-type");
                if (!contentType || !contentType.includes("application/json")) throw new Error("Dosya çok büyük veya sunucu hatası.");
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Hata");
                checkStatus(data.job_id);
            } catch (err) { showError(err.message); }
        }

        function checkStatus(jobId) {
            const interval = setInterval(async () => {
                try {
                    const res = await fetch(`/status/${jobId}`);
                    const data = await res.json();
                    
                    if (data.stage === 'processing' || data.stage === 'saving') {
                        let text = data.stage === 'saving' ? "Kaydediliyor..." : "PDF Küçültülüyor... %" + data.progress;
                        updateProgress(data.progress || 0, text);
                    } else if (data.stage === 'completed') {
                        clearInterval(interval);
                        updateProgress(100, "Tamamlandı!");
                        setTimeout(() => {
                            document.getElementById('processSection').classList.add('hidden');
                            document.getElementById('resultSection').classList.remove('hidden');
                            document.getElementById('statsBox').innerHTML = `✅ <strong>Hazır!</strong><br>📂 Orijinal: ${data.stats.original}<br>📉 Yeni: ${data.stats.optimized}`;
                            document.getElementById('downloadLink').href = data.url;
                        }, 500);
                    } else if (data.stage === 'error') { clearInterval(interval); showError(data.message); }
                } catch (e) { clearInterval(interval); showError("Bağlantı kesildi."); }
            }, 1000);
        }

        function updateProgress(p, t) {
            document.getElementById('progressBar').style.width = p + "%";
            document.getElementById('statusText').innerText = t;
        }
        function showError(msg) {
            document.getElementById('uploadSection').classList.add('hidden');
            document.getElementById('processSection').classList.add('hidden');
            document.getElementById('errorSection').classList.remove('hidden');
            document.getElementById('errorBox').innerText = "Hata: " + msg;
        }
    </script>
</body>
</html>
"""

# --- ROUTE'LAR ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# GİZLİLİK ADIM 3: Unutulan dosyaları 5 dakikada bir temizle
def cleanup_old_files():
    while True:
        try:
            cutoff = time.time() - 300 # 5 dakika
            for f in glob.glob(os.path.join(UPLOAD_FOLDER, "*")):
                if os.path.isfile(f) and os.path.getmtime(f) < cutoff:
                    try: os.remove(f)
                    except: pass
        except: pass
        time.sleep(300)

threading.Thread(target=cleanup_old_files, daemon=True).start()

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/upload", methods=["POST"])
def upload_pdf():
    try:
        if 'pdf' not in request.files: return jsonify({"error": "Dosya yok"}), 400
        f = request.files['pdf']
        if f.filename == '' or not allowed_file(f.filename): return jsonify({"error": "Geçersiz dosya"}), 400
        job_id = str(uuid.uuid4())
        filename = secure_filename(f.filename)
        input_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{filename}")
        output_path = os.path.join(UPLOAD_FOLDER, f"opt_{job_id}_{filename}")
        f.save(input_path)
        job_status[job_id] = {"stage": "uploaded", "progress": 0}
        threading.Thread(target=optimize_pdf_task, args=(input_path, output_path, job_id)).start()
        return jsonify({"job_id": job_id})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/status/<job_id>")
def status(job_id):
    info = job_status.get(job_id)
    if not info: return jsonify({"error": "Bulunamadı"}), 404
    res = {"stage": info["stage"], "progress": info.get("progress", 0)}
    if info["stage"] == "completed":
        res["url"] = f"/download/{os.path.basename(info['filename'])}"
        res["stats"] = info["stats"]
    elif info["stage"] == "error": res["message"] = info.get("message", "Hata")
    return jsonify(res)

@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
    
    if not os.path.exists(file_path):
        return "Dosya bulunamadı veya süresi doldu.", 404

    # GİZLİLİK ADIM 2: Dosya indirildikten hemen sonra sil
    response = send_file(file_path, as_attachment=True)

    @response.call_on_close
    def cleanup_after_download():
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                app.logger.info(f"İndirilen dosya silindi: {filename}")
        except Exception as e:
            app.logger.error(f"Silme hatası: {e}")

    return response

@app.errorhandler(413)
def request_entity_too_large(error): return jsonify({"error": "Dosya çok büyük"}), 413
@app.errorhandler(500)
def internal_error(error): return jsonify({"error": "Sunucu hatası"}), 500

if __name__ == "__main__":
    app.run(debug=True)