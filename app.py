# pdf_optimizer_modern.py
import os, subprocess, threading, time
from shutil import which
from flask import Flask, request, send_file, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

compress_status = {}  # {id: {"stage":0-4,"progress":0,"filename":...}}

def find_ghostscript():
    candidates = ["gswin64c","gswin32c","gs"]
    for c in candidates:
        path = which(c)
        if path: return path
    import glob
    paths = glob.glob(r"C:\Program Files\gs\*\bin\gswin64c.exe") + \
            glob.glob(r"C:\Program Files (x86)\gs\*\bin\gswin32c.exe")
    return sorted(paths)[-1] if paths else None

def compress_pdf(input_path, output_path, upload_id):
    compress_status[upload_id]["stage"] = 1  # Sıkıştırma
    compress_status[upload_id]["progress"] = 0
    gs = find_ghostscript()
    if not gs:
        compress_status[upload_id]["stage"] = -1
        return
    # Compress simülasyonu
    total_time = 3
    steps = int(total_time/0.05)
    for i in range(steps):
        time.sleep(0.05)
        compress_status[upload_id]["progress"] = int((i/steps)*90)
    # Gerçek compress
    subprocess.run([
        gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
        "-dPDFSETTINGS=/ebook", "-dNOPAUSE","-dQUIET","-dBATCH",
        f"-sOutputFile={output_path}", input_path
    ], check=True)
    # Küçültülüyor aşaması
    compress_status[upload_id]["stage"] = 2
    for i in range(10):
        time.sleep(0.1)
        compress_status[upload_id]["progress"] = 90 + int((i+1)/10*10)
    # Bitmek üzere aşaması
    compress_status[upload_id]["stage"] = 3
    for i in range(5):
        time.sleep(0.1)
        compress_status[upload_id]["progress"] = 100
    compress_status[upload_id]["stage"] = 4  # Tamamlandı

@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Modern PDF Optimize</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Poppins',sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;justify-content:center;align-items:center;color:#fff;}
.container{background:rgba(255,255,255,0.1);backdrop-filter:blur(25px);padding:50px 40px;border-radius:25px;box-shadow:0 15px 40px rgba(0,0,0,0.3);text-align:center;width:95%;max-width:550px;transition:all 0.3s;}
h1{font-size:3rem;margin-bottom:15px;letter-spacing:1px;text-shadow:1px 1px 5px rgba(0,0,0,0.3);}
p{font-size:1.2rem;margin-bottom:40px;color:#f1f1f1;line-height:1.4;}
#fileLabel{padding:20px 40px;background:linear-gradient(90deg,#ff7eb3,#ff758c);border:none;border-radius:15px;cursor:pointer;font-weight:700;color:white;font-size:1.2rem;display:inline-block;margin-bottom:20px;transition:all 0.3s ease;box-shadow:0 5px 20px rgba(0,0,0,0.2);}
#fileLabel:hover{transform:scale(1.05);box-shadow:0 8px 25px rgba(0,0,0,0.3);}
#pdf{display:none;}
#fileName{font-weight:600;margin-bottom:25px;font-size:1rem;}
.progress-container{width:100%;background:rgba(255,255,255,0.15);border-radius:25px;overflow:hidden;height:35px;display:none;position:relative;margin-bottom:30px;box-shadow:inset 0 0 10px rgba(0,0,0,0.2);}
.progress{height:100%;width:0%;background:linear-gradient(90deg,#ff7eb3,#ff758c);transition:width 0.3s ease;}
.progress-text{position:absolute;width:100%;text-align:center;top:0;left:0;line-height:35px;font-weight:600;font-size:1rem;text-shadow:1px 1px 3px rgba(0,0,0,0.3);}
#downloadBtn{display:none;padding:15px 40px;font-size:1.2rem;font-weight:700;background:linear-gradient(90deg,#ff7eb3,#ff758c);color:white;border:none;border-radius:20px;cursor:pointer;text-decoration:none;transition:all 0.3s ease;box-shadow:0 5px 20px rgba(0,0,0,0.2);}
#downloadBtn:hover{transform:scale(1.05);box-shadow:0 8px 25px rgba(0,0,0,0.3);}
@media(max-width:600px){.container{padding:40px 20px;} h1{font-size:2.2rem;} p{font-size:1rem;} #fileLabel,#downloadBtn{padding:15px 30px;font-size:1rem;}}
</style>
</head>
<body>
<div class="container">
<h1>📄 PDF Optimize</h1>
<p>PDF dosyanızı yükleyin ve boyutunu küçültün!</p>

<label id="fileLabel" for="pdf">📂 PDF Seç</label>
<input type="file" id="pdf" accept="application/pdf">
<div id="fileName"></div>

<div class="progress-container" id="progressContainer">
    <div class="progress" id="progress"></div>
    <div class="progress-text" id="progressText">Yükleniyor...</div>
</div>

<a id="downloadBtn" href="#" download>⬇️ PDF İndir</a>
</div>

<script>
const pdfInput=document.getElementById('pdf');
const fileName=document.getElementById('fileName');
const progressContainer=document.getElementById('progressContainer');
const progress=document.getElementById('progress');
const progressText=document.getElementById('progressText');
const downloadBtn=document.getElementById('downloadBtn');

let uploadId="";
let stage=0;

pdfInput.addEventListener('change',()=>{
    if(pdfInput.files[0]){
        fileName.innerText="Seçilen dosya: "+pdfInput.files[0].name;
        uploadFile();
    }
});

function uploadFile(){
    uploadId=Math.random().toString(36).substr(2,9);
    progressContainer.style.display="block";
    progress.style.width="0%";
    progressText.innerText="Yükleniyor...";

    const formData=new FormData();
    formData.append('pdf',pdfInput.files[0]);

    const xhr=new XMLHttpRequest();
    xhr.open('POST','/upload/'+uploadId);

    xhr.upload.onprogress=function(e){
        if(e.lengthComputable){
            let percent=Math.round((e.loaded/e.total)*100);
            progress.style.width=percent+"%";
        }
    };

    xhr.onload=function(){
        if(xhr.status===200){
            stage=1;
            simulateStages();
        } else {progressText.innerText="Hata oluştu!";}
    };
    xhr.onerror=function(){progressText.innerText="Hata oluştu!";}
    xhr.send(formData);
}

function simulateStages(){
    const interval=setInterval(()=>{
        fetch('/status/'+uploadId).then(r=>r.json()).then(data=>{
            let prog=data.progress;
            progress.style.width=prog+"%";
            switch(data.stage){
                case 0: progressText.innerText="Yükleniyor..."; break;
                case 1: progressText.innerText="Sıkıştırılıyor..."; break;
                case 2: progressText.innerText="Küçültülüyor..."; break;
                case 3: progressText.innerText="Bitmek Üzere..."; break;
                case 4:
                    progress.style.width="100%";
                    progressText.innerText="PDF Hazır!";
                    clearInterval(interval);
                    progressContainer.style.display="none";
                    downloadBtn.href=data.url;
                    downloadBtn.style.display="inline-block";
                    break;
            }
        });
    },150);
}
</script>
</body>
</html>
"""

# Upload endpoint
@app.route("/upload/<upload_id>",methods=["POST"])
def upload_pdf(upload_id):
    f=request.files.get("pdf")
    if not f or not f.filename.lower().endswith(".pdf"):
        return jsonify({"error":"Geçerli PDF yükleyin"}),400
    filename=secure_filename(f.filename)
    in_path=os.path.join(UPLOAD_FOLDER,filename)
    out_path=os.path.join(UPLOAD_FOLDER,"optimized_"+filename)
    f.save(in_path)
    compress_status[upload_id]={"stage":0,"progress":0,"filename":filename}
    threading.Thread(target=compress_pdf,args=(in_path,out_path,upload_id)).start()
    return jsonify({"message":"Upload tamamlandı"})

# Status endpoint
@app.route("/status/<upload_id>")
def status(upload_id):
    status=compress_status.get(upload_id)
    if not status:
        return jsonify({"stage":0,"progress":0})
    url=""
    if status["stage"]==4:
        url=f"/download/optimized_{status['filename']}"
    return jsonify({"stage":status["stage"],"progress":status["progress"],"url":url})

# Download endpoint
@app.route("/download/<filename>")
def download_file(filename):
    return send_file(os.path.join(UPLOAD_FOLDER,filename),as_attachment=True)

if __name__=="__main__":
    print("Sunucu çalışıyor: http://127.0.0.1:5000")
    app.run(debug=True)
