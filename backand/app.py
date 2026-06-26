import os
import json
import zipfile
import tempfile
import shutil
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv
import time

load_dotenv()

app = Flask(__name__)
CORS(app)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SYSTEM_PROMPT = ""

# تحميل الـ system prompt من الملف
def load_system_prompt():
    global SYSTEM_PROMPT
    try:
        with open("system_prompt.md", "r", encoding="utf-8") as f:
            SYSTEM_PROMPT = f.read()
    except:
        SYSTEM_PROMPT = "You are a senior code auditor. Output JSON only."

load_system_prompt()

# امتدادات الملفات النصية المسموح بفحصها
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
    
    # قص المحتوى إذا كان طويلاً جداً (لحماية التوكنات)
    if len(content) > 15000:
        content = content[:15000] + "\n\n... [مقتطع لطول الملف]"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "Shadow Code Auditor"
    }

    payload = {
        "model": "mistralai/mistral-large-2407",  # قوي وسريع للتجربة
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
            # محاولة استخراج JSON من النص (أحياناً يحط markdown)
            try:
                return json.loads(ai_message)
            except:
                # محاولة تنظيف النص
                import re
                json_match = re.search(r'\{.*\}', ai_message, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    return {"file": filename, "summary": "خطأ في تحليل مخرجات الذكاء", "issues": [], "score": 0}
        else:
            return {"file": filename, "summary": f"فشل الاتصال بالذكاء ({response.status_code})", "issues": [], "score": 0}
    except Exception as e:
        return {"file": filename, "summary": f"استثناء: {str(e)}", "issues": [], "score": 0}

@app.route('/upload', methods=['POST'])
def upload_zip():
    if 'file' not in request.files:
        return jsonify({"error": "لا يوجد ملف مرفق"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "اسم الملف فارغ"}), 400

    # إنشاء مجلد مؤقت
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, file.filename)
    file.save(zip_path)

    results = []
    total_files = 0
    analyzed_files = 0

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # التجوال في الملفات المستخرجة
        for root, dirs, files in os.walk(temp_dir):
            # تخطي مجلدات النظام والمجلدات المخفية
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
                    time.sleep(0.5)  # تجنب حد الـ rate limit
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
        # تنظيف المجلد المؤقت
        shutil.rmtree(temp_dir, ignore_errors=True)

    # حساب المتوسط العام
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

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
