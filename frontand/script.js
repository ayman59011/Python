const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const loader = document.getElementById('loader');
const progressText = document.getElementById('progressText');
const progressFill = document.getElementById('progressFill');
const resultsDiv = document.getElementById('results');
const totalFiles = document.getElementById('totalFiles');
const analyzedFiles = document.getElementById('analyzedFiles');
const overallScore = document.getElementById('overallScore');
const issuesList = document.getElementById('issuesList');

let selectedFile = null;

uploadBtn.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});

fileInput.addEventListener('change', () => {
    if (fileInput.files.length) handleFile(fileInput.files[0]);
});

function handleFile(file) {
    if (!file.name.endsWith('.zip')) { alert('ارفع ملف ZIP فقط!'); return; }
    selectedFile = file;
    fileName.textContent = file.name;
    fileSize.textContent = (file.size / 1024).toFixed(2) + ' KB';
    fileInfo.style.display = 'block';
    uploadFile(file);
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    loader.style.display = 'block';
    resultsDiv.style.display = 'none';
    progressFill.style.width = '0%';
    progressText.textContent = 'جاري رفع الملف...';

    try {
        const response = await fetch('http://localhost:5000/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        // محاكاة تقدم المعالجة (لأنها غير متدفقة)
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 10;
            if (progress > 95) clearInterval(interval);
            progressFill.style.width = Math.min(progress, 95) + '%';
            progressText.textContent = `جاري تمزيق الملفات... ${Math.floor(Math.min(progress, 95))}%`;
        }, 300);

        const data = await response.json();
        clearInterval(interval);
        progressFill.style.width = '100%';
        progressText.textContent = 'اكتمل التمزيق!';

        setTimeout(() => {
            loader.style.display = 'none';
            displayResults(data);
        }, 500);

    } catch (error) {
        progressText.textContent = '❌ فشل الاتصال بالخادم أو انتهت المهلة';
        console.error(error);
    }
}

function displayResults(data) {
    resultsDiv.style.display = 'block';
    totalFiles.textContent = data.total_files || 0;
    analyzedFiles.textContent = data.analyzed_files || 0;
    overallScore.textContent = data.overall_score || 0;

    issuesList.innerHTML = '';
    if (data.details && data.details.length) {
        data.details.forEach(item => {
            const card = document.createElement('div');
            card.className = 'issue-card';
            
            let issuesHtml = '';
            if (item.issues && item.issues.length) {
                item.issues.forEach(issue => {
                    const severityClass = issue.severity === 'عالي' ? 'severity-high' : 
                                         issue.severity === 'متوسط' ? 'severity-medium' : 'severity-low';
                    issuesHtml += `
                        <div class="issue-item">
                            <div><span class="${severityClass}">[${issue.severity || 'متوسط'}]</span> 
                            <strong>${issue.type || 'ثغرة'}</strong> - ${issue.description || ''}</div>
                            <div class="solution">🛠️ الحل: ${issue.solution || 'غير محدد'}</div>
                        </div>
                    `;
                });
            } else {
                issuesHtml = '<div style="color: #64ffda; padding: 0.5rem;">✅ لا توجد مشاكل مكتشفة.</div>';
            }

            card.innerHTML = `
                <div class="file-path">📄 ${item.file || 'غير معروف'}</div>
                <div class="summary">${item.summary || ''}</div>
                ${issuesHtml}
            `;
            issuesList.appendChild(card);
        });
    }
}
