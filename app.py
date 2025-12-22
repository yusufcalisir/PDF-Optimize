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

# --- SIKIŞTIRMA MOTORU ---
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
        
        compress_pdf_aggressive(input_path, output_path, job_id)
            
        original_size = os.path.getsize(input_path)
        optimized_size = os.path.getsize(output_path)
        
        # Orijinal dosyayı sil
        if os.path.exists(input_path):
            os.remove(input_path)
        
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
        app.logger.error(f"Hata: {e}")
        job_status[job_id]["stage"] = "error"
        job_status[job_id]["message"] = "İşlem sırasında hata oluştu."
        if os.path.exists(input_path): os.remove(input_path)

# --- HTML TASARIM ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Optimize</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📄</text></svg>">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body { 
            font-family: 'Inter', sans-serif; 
            background: radial-gradient(circle at center, #1e293b, #0f172a, #020617);
            min-height: 100vh; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            color: #e2e8f0; 
            transition: all 0.3s ease;
            overflow-x: hidden;
        }
        
        /* DİL SEÇİM BUTONLARI */
        .lang-container {
            position: absolute;
            top: 25px;
            right: 25px;
            display: flex;
            gap: 6px;
            z-index: 1000;
            direction: ltr !important;
            flex-wrap: nowrap;
            max-width: 100vw;
            overflow-x: auto;
            scrollbar-width: none;
            -ms-overflow-style: none;
        }
        .lang-container::-webkit-scrollbar { display: none; }
        
        .lang-btn {
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #94a3b8;
            padding: 8px 12px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.75rem;
            font-weight: 700;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            letter-spacing: 0.5px;
            backdrop-filter: blur(4px);
            white-space: nowrap;
            flex-shrink: 0;
        }
        
        .lang-btn:hover {
            color: #00f2ff;
            border-color: #00f2ff;
            box-shadow: 0 0 10px rgba(0, 242, 255, 0.3);
            transform: translateY(-2px);
        }
        
        .lang-btn.active {
            background: rgba(0, 242, 255, 0.1);
            color: #00f2ff;
            border-color: #00f2ff;
            box-shadow: 0 0 15px rgba(0, 242, 255, 0.2);
        }

        @media (max-width: 768px) {
            .lang-container {
                top: 0; right: 0; left: 0;
                justify-content: center;
                padding: 15px 10px;
                background: rgba(15, 23, 42, 0.8);
                backdrop-filter: blur(10px);
                border-bottom: 1px solid rgba(255,255,255,0.05);
                width: 100%;
            }
            .container { margin-top: 60px; padding: 40px 20px; width: 90%; }
            h1 { font-size: 2rem; }
            .btn { width: 100%; padding: 18px 20px; }
        }

        .container { 
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(30px); 
            -webkit-backdrop-filter: blur(30px); 
            padding: 60px 40px; 
            border-radius: 30px; 
            box-shadow: 0 30px 60px -12px rgba(0, 0, 0, 0.8); 
            text-align: center; 
            width: 95%; 
            max-width: 500px; 
            border: 1px solid rgba(0, 242, 255, 0.15); 
            position: relative; 
            overflow: hidden;
        }
        
        .container::before {
            content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, transparent, #00f2ff, transparent);
            opacity: 0.8; box-shadow: 0 0 15px #00f2ff;
        }

        h1 { 
            font-size: 2.5rem; margin-bottom: 15px; letter-spacing: -1px; font-weight: 800;
            background: linear-gradient(to right, #fff, #94a3b8);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        
        .subtitle { 
            font-size: 0.9rem; margin-bottom: 40px; color: #94a3b8; 
            background: rgba(0,0,0,0.4); padding: 8px 20px; border-radius: 50px; 
            display: inline-block; border: 1px solid rgba(255,255,255,0.05);
            line-height: 1.5;
        }

        .btn { 
            padding: 20px 45px; background: linear-gradient(135deg, #0ea5e9, #2563eb); 
            border: none; border-radius: 16px; cursor: pointer; font-weight: 700; color: white; 
            font-size: 1.1rem; display: inline-block; transition: all 0.3s ease; 
            box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.4); text-decoration: none; 
            margin-top: 15px; position: relative; overflow: hidden;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 30px -10px rgba(37, 99, 235, 0.6); filter: brightness(1.1); }

        .secondary-btn { 
            background: transparent; border: 1px solid rgba(255,255,255,0.1); color: #94a3b8;
            margin-top: 25px; font-size: 0.9rem; padding: 12px 30px; box-shadow: none;
        }
        .secondary-btn:hover { background: rgba(255,255,255,0.05); color: #fff; border-color: rgba(255,255,255,0.2); }

        .progress-container { 
            width: 100%; background-color: rgba(0, 0, 0, 0.4); border-radius: 12px; 
            margin: 25px 0; height: 8px; overflow: hidden; 
        }
        .progress-bar { 
            width: 0%; height: 100%; background: #00f2ff; box-shadow: 0 0 15px rgba(0, 242, 255, 0.5); 
            transition: width 0.4s ease; border-radius: 12px;
        }

        .stats-box { 
            background: rgba(2, 6, 23, 0.6); padding: 20px; border-radius: 16px; 
            margin-bottom: 30px; text-align: left; border: 1px solid rgba(0, 242, 255, 0.1);
        }
        .stats-box strong { color: #00f2ff; }

        .hidden { display: none !important; }
        .file-name { margin-top: 15px; font-weight: 500; color: #00f2ff; font-size: 0.9rem;}
        .error-box { background: rgba(220, 38, 38, 0.1); color: #f87171; padding: 15px; border-radius: 12px; margin-bottom: 20px; border: 1px solid rgba(220, 38, 38, 0.2); }
        
        body[dir="rtl"] { direction: rtl; }
        body[dir="rtl"] .stats-box { text-align: right; }
    </style>
</head>
<body>
    <div class="lang-container">
        <button class="lang-btn active" onclick="setLang('tr')">TR</button>
        <button class="lang-btn" onclick="setLang('en')">EN</button>
        <button class="lang-btn" onclick="setLang('de')">DE</button>
        <button class="lang-btn" onclick="setLang('fr')">FR</button>
        <button class="lang-btn" onclick="setLang('it')">IT</button>
        <button class="lang-btn" onclick="setLang('es')">ES</button>
        <button class="lang-btn" onclick="setLang('ar')">AR</button>
    </div>

    <div class="container">
        <h1 id="txt_title">📄 PDF Optimize</h1>
        <div class="subtitle" id="txt_subtitle">Kaliteden ödün vermeden boyut küçültün<br>🔒 Güvenli & Otomatik Silinen Dosyalar</div>

        <div id="uploadSection">
            <input type="file" id="fileInput" accept="application/pdf" style="display: none;">
            <label for="fileInput" class="btn" id="txt_selectBtn">📂 PDF Seç</label>
            <div id="selectedFileName" class="file-name"></div>
        </div>

        <div id="processSection" class="hidden">
            <div class="progress-container"><div class="progress-bar" id="progressBar"></div></div>
            <div id="statusText" style="font-weight: 600; font-size: 0.9rem; color: #94a3b8;">...</div>
        </div>

        <div id="resultSection" class="hidden">
            <div id="statsBox" class="stats-box"></div>
            <a id="downloadLink" href="#" class="btn"><span id="txt_downloadBtn">⬇️ İndir</span></a>
            <br>
            <button class="btn secondary-btn" onclick="location.reload()" id="txt_newFileBtn">Yeni Dosya</button>
        </div>

        <div id="errorSection" class="hidden">
            <div id="errorBox" class="error-box"></div>
            <button class="btn secondary-btn" onclick="location.reload()" id="txt_retryBtn">Tekrar Dene</button>
        </div>
    </div>

    <script>
        const translations = {
            tr: {
                title: "📄 PDF Optimize",
                subtitle: "Kaliteden ödün vermeden boyut küçültün<br>🔒 Güvenli & Otomatik Silinen Dosyalar",
                selectBtn: "📂 PDF Dosyası Seç",
                selected: "Seçilen: ",
                uploading: "Yükleniyor...",
                processing: "İşleniyor... %",
                saving: "Kaydediliyor...",
                completed: "Tamamlandı!",
                successTitle: "✅ İşlem Başarılı!",
                original: "📂 Orijinal: ",
                newSize: "📉 Yeni Boyut: ",
                downloadBtn: "⬇️ İndir ve Sil",
                newFileBtn: "Yeni İşlem",
                retryBtn: "Tekrar Dene",
                errorServer: "Hata oluştu."
            },
            en: {
                title: "📄 PDF Optimize",
                subtitle: "Reduce size without losing quality<br>🔒 Secure & Auto-Deleted Files",
                selectBtn: "📂 Select PDF File",
                selected: "Selected: ",
                uploading: "Uploading...",
                processing: "Processing... %",
                saving: "Saving...",
                completed: "Completed!",
                successTitle: "✅ Success!",
                original: "📂 Original: ",
                newSize: "📉 New Size: ",
                downloadBtn: "⬇️ Download & Delete",
                newFileBtn: "New Task",
                retryBtn: "Try Again",
                errorServer: "An error occurred."
            },
            de: {
                title: "📄 PDF Optimieren",
                subtitle: "Größe reduzieren ohne Qualitätsverlust<br>🔒 Sichere & Automatisch Gelöschte Dateien",
                selectBtn: "📂 PDF Auswählen",
                selected: "Ausgewählt: ",
                uploading: "Hochladen...",
                processing: "Verarbeiten... %",
                saving: "Speichern...",
                completed: "Fertig!",
                successTitle: "✅ Erfolgreich!",
                original: "📂 Original: ",
                newSize: "📉 Neu: ",
                downloadBtn: "⬇️ Laden & Löschen",
                newFileBtn: "Neue Aufgabe",
                retryBtn: "Erneut versuchen",
                errorServer: "Ein Fehler ist aufgetreten."
            },
            fr: {
                title: "📄 Optimiser PDF",
                subtitle: "Réduire la taille sans perte de qualité<br>🔒 Fichiers Sécurisés & Supprimés Auto.",
                selectBtn: "📂 Choisir PDF",
                selected: "Sélectionné : ",
                uploading: "Envoi...",
                processing: "Traitement... %",
                saving: "Enregistrement...",
                completed: "Terminé !",
                successTitle: "✅ Succès !",
                original: "📂 Original : ",
                newSize: "📉 Nouveau : ",
                downloadBtn: "⬇️ Télécharger",
                newFileBtn: "Nouveau",
                retryBtn: "Réessayer",
                errorServer: "Une erreur est survenue."
            },
            it: {
                title: "📄 Ottimizza PDF",
                subtitle: "Riduci le dimensioni senza perdere qualità<br>🔒 File Sicuri & Eliminazione Auto.",
                selectBtn: "📂 Seleziona PDF",
                selected: "Selezionato: ",
                uploading: "Caricamento...",
                processing: "Elaborazione... %",
                saving: "Salvataggio...",
                completed: "Completato!",
                successTitle: "✅ Successo!",
                original: "📂 Originale: ",
                newSize: "📉 Nuovo: ",
                downloadBtn: "⬇️ Scarica",
                newFileBtn: "Nuovo",
                retryBtn: "Riprova",
                errorServer: "Si è verificato un errore."
            },
            es: {
                title: "📄 Optimizar PDF",
                subtitle: "Reducir tamaño sin perder calidad<br>🔒 Archivos Seguros y Eliminación Auto.",
                selectBtn: "📂 Elegir PDF",
                selected: "Seleccionado: ",
                uploading: "Subiendo...",
                processing: "Procesando... %",
                saving: "Guardando...",
                completed: "¡Completado!",
                successTitle: "✅ ¡Éxito!",
                original: "📂 Original: ",
                newSize: "📉 Nuevo: ",
                downloadBtn: "⬇️ Descargar",
                newFileBtn: "Nuevo",
                retryBtn: "Reintentar",
                errorServer: "Ocurrió un error."
            },
            ar: {
                title: "📄 تحسين PDF",
                subtitle: "تقليل الحجم دون فقدان الجودة<br>🔒 ملفات آمنة وحذف تلقائي",
                selectBtn: "📂 اختر ملف PDF",
                selected: "المحدد: ",
                uploading: "جارٍ التحميل...",
                processing: "جارٍ المعالجة... %",
                saving: "جارٍ الحفظ...",
                completed: "اكتمل!",
                successTitle: "✅ تم بنجاح!",
                original: "📂 الأصل: ",
                newSize: "📉 الجديد: ",
                downloadBtn: "⬇️ تنزيل وحذف",
                newFileBtn: "ملف جديد",
                retryBtn: "حاول مرة أخرى",
                errorServer: "حدث خطأ ما."
            }
        };

        let currentLang = 'tr';

        function setLang(lang) {
            currentLang = lang;
            const t = translations[lang];

            if (lang === 'ar') { document.body.setAttribute('dir', 'rtl'); }
            else { document.body.setAttribute('dir', 'ltr'); }

            document.getElementById('txt_title').innerText = t.title;
            // HTML içeriği olarak ata (br etiketi için)
            document.getElementById('txt_subtitle').innerHTML = t.subtitle;
            document.getElementById('txt_selectBtn').innerText = t.selectBtn;
            document.getElementById('txt_downloadBtn').innerText = t.downloadBtn;
            document.getElementById('txt_newFileBtn').innerText = t.newFileBtn;
            document.getElementById('txt_retryBtn').innerText = t.retryBtn;

            document.querySelectorAll('.lang-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
        }

        const fileInput = document.getElementById('fileInput');
        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            document.getElementById('selectedFileName').innerText = translations[currentLang].selected + file.name;
            startUpload(file);
        });

        // XHR ile Yükleme (Progress Bar Destekli)
        function startUpload(file) {
            document.getElementById('uploadSection').classList.add('hidden');
            document.getElementById('processSection').classList.remove('hidden');
            
            // Sıfırla
            updateProgress(0, translations[currentLang].uploading + " %0");

            const formData = new FormData();
            formData.append('pdf', file);

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload', true);

            // Yükleme Takibi
            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 100);
                    // %99'da takılı kalmasın, backend işlemeye geçince metin değişecek
                    let text = translations[currentLang].uploading + " %" + percentComplete;
                    updateProgress(percentComplete, text);
                }
            };

            xhr.onload = function() {
                if (xhr.status === 200) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        checkStatus(data.job_id);
                    } catch (e) {
                        showError(translations[currentLang].errorServer);
                    }
                } else {
                    showError(translations[currentLang].errorServer);
                }
            };

            xhr.onerror = function() {
                showError("Bağlantı hatası.");
            };

            xhr.send(formData);
        }

        function checkStatus(jobId) {
            const interval = setInterval(async () => {
                try {
                    const res = await fetch(`/status/${jobId}`);
                    const data = await res.json();
                    
                    if (data.stage === 'processing' || data.stage === 'saving') {
                        let t = translations[currentLang];
                        let text = data.stage === 'saving' ? t.saving : t.processing + data.progress;
                        updateProgress(data.progress || 0, text);
                    } else if (data.stage === 'completed') {
                        clearInterval(interval);
                        updateProgress(100, translations[currentLang].completed);
                        setTimeout(() => {
                            document.getElementById('processSection').classList.add('hidden');
                            document.getElementById('resultSection').classList.remove('hidden');
                            
                            let t = translations[currentLang];
                            document.getElementById('statsBox').innerHTML = `
                                <strong>${t.successTitle}</strong><br><br>
                                ${t.original}${data.stats.original}<br>
                                ${t.newSize}${data.stats.optimized}
                            `;
                            document.getElementById('downloadLink').href = data.url;
                        }, 500);
                    } else if (data.stage === 'error') { clearInterval(interval); showError(data.message); }
                } catch (e) { clearInterval(interval); showError("Connection error"); }
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

# --- İNDİRME VE SİLME ---
@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
    if not os.path.exists(file_path): return "Dosya bulunamadı veya süresi doldu.", 404
    try:
        return_data = io.BytesIO()
        with open(file_path, 'rb') as f: return_data.write(f.read())
        return_data.seek(0)
        os.remove(file_path)
        app.logger.info(f"Dosya diskten silindi, RAM'den gönderiliyor: {filename}")
        return send_file(return_data, as_attachment=True, download_name=filename, mimetype='application/pdf')
    except Exception as e: return "İndirme hatası.", 500

# --- DİĞER ROUTE'LAR ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_old_files():
    while True:
        try:
            cutoff = time.time() - 300 
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

@app.errorhandler(413)
def request_entity_too_large(error): return jsonify({"error": "Dosya çok büyük"}), 413
@app.errorhandler(500)
def internal_error(error): return jsonify({"error": "Sunucu hatası"}), 500

if __name__ == "__main__":
    app.run(debug=True)
