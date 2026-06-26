import os
import json
import zipfile
import tempfile
import shutil
import time
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)  # يظل مفعلاً للاحتياط، لكننا الآن نخدم الواجهة من نفس الدومين

# ==================== إعداد مسار الواجهة الأمامية ====================
# نفترض أن مجلد 'frontend' موجود في نفس مستوى 'backend'
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '../frontend')

# ==================== تحميل System Prompt ====================
SYSTEM_PROMPT = ""
def load_system_prompt():
    global SYSTEM_PROMPT
    try:
        with open("system_prompt.md", "r", encoding="utf-8") as f:
            SYSTEM_PROMPT = f.read()
    except:
        SYSTEM_PROMPT = "You are a senior code auditor. Output JSON only."

load_system_prompt()

# ==================== إعدادات OpenRouter ====================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ==================== دوال مساعدة للتحليل ====================
TEXT_EXTENSIONS = {
    '.py', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml',
    '.txt', '.md', '.sql', '.sh', '.bat', '.ps1', '.ts', '.jsx', '.tsx',
    '.vue', '.php', '.rb', '.go', '.rs', '.c', '.cpp', '.h', '.java'
}

def is_text_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in TEXT_EXTENSIONS

def read_file_safely(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
        except:
            return None

def analyze_file_with_ai(filename, content):
    if content is None:
        return {"file": filename, "summary": "ملف ثنائي أو غير قابل للقراءة", "issues": [], "score": 0}
    
    if len(content) > 15000:
        content = content[:15000] + "\n\n... [مقتطع لطول الملف]"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "Shadow Code Auditor"
    }

    payload = {
        "model": "mistralai/mistral-large-2407",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"قم بتحليل هذا الملف بدقة: {filename}\n\nمحتوى الملف:\n```\n{content}\n```"}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            ai_message = data['choices'][0]['message']['content']
            try:
                return json.loads(ai_message)
            except:
                json_match = re.search(r'\{.*\}', ai_message, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    return {"file": filename, "summary": "خطأ في تحليل مخرجات الذكاء", "issues": [], "score": 0}
        else:
            return {"file": filename, "summary": f"فشل الاتصال بالذكاء ({response.status_code})", "issues": [], "score": 0}
    except Exception as e:
        return {"file": filename, "summary": f"استثناء: {str(e)}", "issues": [], "score": 0}

# ==================== نقاط النهاية (Endpoints) ====================

# 1. خدمة الواجهة الأمامية (الصفحة الرئيسية)
@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

# 2. خدمة الملفات الثابتة (CSS, JS, صور...)
@app.route('/<path:path>')
def serve_static_files(path):
    # التأكد من أن الملف موجود فعلياً في مجلد frontend
    if os.path.exists(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    # إذا لم يكن موجوداً (مثلاً مسار SPA)، نعيد index.html لتتفادى الخطأ 404
    return send_from_directory(FRONTEND_DIR, 'index.html')

# 3. نقطة رفع الملفات وتحليلها (الوظيفة الأساسية)
@app.route('/upload', methods=['POST'])
def upload_zip():
    if 'file' not in request.files:
        return jsonify({"error": "لا يوجد ملف مرفق"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "اسم الملف فارغ"}), 400

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, file.filename)
    file.save(zip_path)

    results = []
    total_files = 0
    analyzed_files = 0

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        for root, dirs, files in os.walk(temp_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
            for f in files:
                if f.startswith('.') or f in ['package-lock.json']:
                    continue
                file_path = os.path.join(root, f)
                relative_path = os.path.relpath(file_path, temp_dir)
                total_files += 1

                if is_text_file(f):
                    analyzed_files += 1
                    content = read_file_safely(file_path)
                    result = analyze_file_with_ai(relative_path, content)
                    results.append(result)
                    time.sleep(0.5)
                else:
                    results.append({
                        "file": relative_path,
                        "summary": "ملف ثنائي (تم تخطي التحليل)",
                        "issues": [],
                        "score": 0
                    })
    
    except Exception as e:
        return jsonify({"error": f"حدث خطأ أثناء فك الضغط: {str(e)}"}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    total_score = 0
    valid_scores = 0
    for r in results:
        if 'score' in r and isinstance(r['score'], (int, float)):
            total_score += r['score']
            valid_scores += 1
    avg_score = round(total_score / valid_scores, 2) if valid_scores > 0 else 0

    return jsonify({
        "status": "completed",
        "total_files": total_files,
        "analyzed_files": analyzed_files,
        "overall_score": avg_score,
        "details": results
    })

# ==================== تشغيل الخادم ====================
if __name__ == '__main__':
    # Render سيحدد المنفذ تلقائياً عبر المتغير البيئي PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
