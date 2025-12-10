// API 베이스 URL
const API_BASE = window.location.origin;

// 타임아웃 설정 (초)
const TIMEOUT_SECONDS = 3;

// 로그 저장
let logMessages = [];

// 데이터 갱신
async function updateDashboard() {
    try {
        // 시스템 상태
        const statusRes = await fetch(`${API_BASE}/api/status`);
        const status = await statusRes.json();

        // 시간 업데이트
        document.getElementById('server-time').textContent = `⏰ ${status.server_time}`;

        // DB 상태
        const dbStatus = document.getElementById('db-status');
        if (status.db_connected) {
            dbStatus.textContent = '✅ DB 연결';
            dbStatus.className = 'connected';
        } else {
            dbStatus.textContent = '⚠️ DB 끊김';
            dbStatus.className = 'disconnected';
        }

        // 최신 데이터
        const dataRes = await fetch(`${API_BASE}/api/latest_data`);
        const latestData = await dataRes.json();

        // 테이블 업데이트
        updateTable(latestData);

        // 로그 업데이트 (5초마다)
        updateLogs();
    } catch (error) {
        console.error('데이터 갱신 오류:', error);
        addLog('❌ 데이터 갱신 오류: ' + error.message);
    }
}

// 로그 업데이트 (서버에서 가져오기)
async function updateLogs() {
    try {
        const res = await fetch(`${API_BASE}/api/logs`);
        const logs = await res.json();

        // 로그 컨테이너에 표시 (최신 10개만)
        const logContainer = document.getElementById('log-container');
        const recentLogs = logs.slice(-10).reverse();

        logContainer.innerHTML = recentLogs
            .map((log) => `<div class="log-line">[${log.timestamp}] 💾 ${log.message}</div>`)
            .join('');
    } catch (error) {
        console.error('로그 갱신 오류:', error);
    }
}

// 테이블 업데이트
function updateTable(data) {
    const tbody = document.getElementById('hospital-tbody');

    if (Object.keys(data).length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="no-data">등록된 병원이 없습니다</td></tr>';
        return;
    }

    let html = '';
    let index = 1;

    // 병원명 순 정렬
    const sortedData = Object.entries(data).sort((a, b) => a[0].localeCompare(b[0]));

    for (const [hospitalKey, info] of sortedData) {
        // 통신 상태 확인
        const lastTime = new Date(info.timestamp);
        const now = new Date();
        const diffSeconds = Math.floor((now - lastTime) / 1000);
        const isOffline = diffSeconds > TIMEOUT_SECONDS;

        const hospitalClass = isOffline ? 'offline-hospital' : '';

        html += `
            <tr>
                <td>${index}</td>
                <td class="${hospitalClass}">
                    ${hospitalKey} (${info.ip}:${info.port})
                </td>
                <td class="${hospitalClass}">${info.value.toLocaleString('ko-KR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}</td>
                <td style="text-align: center;">
                    <button class="delete-btn" onclick="deleteHospital('${hospitalKey}')">🗑️ 삭제</button>
                </td>
            </tr>
        `;
        index++;
    }

    tbody.innerHTML = html;
}

// 병원 삭제
function deleteHospital(hospitalKey) {
    if (confirm(`${hospitalKey}을(를) 삭제하시겠습니까?`)) {
        addLog(`🗑️ ${hospitalKey} 삭제`);
        updateDashboard();
    }
}

// 로컬 로그 추가 (사용자 액션용)
function addLog(message) {
    const now = new Date();
    const timestamp = now.toTimeString().split(' ')[0];
    const logLine = `[${timestamp}] ${message}`;

    logMessages.push(logLine);

    if (logMessages.length > 100) {
        logMessages.shift();
    }
}

// CSV 내보내기 다이얼로그
async function showExportDialog() {
    const res = await fetch(`${API_BASE}/api/latest_data`);
    const data = await res.json();

    const hospitalSelect = document.getElementById('hospital-select');
    hospitalSelect.innerHTML = '';

    if (Object.keys(data).length === 0) {
        alert('등록된 병원이 없습니다.');
        return;
    }

    for (const key in data) {
        const option = document.createElement('option');
        option.value = key;
        option.textContent = key;
        hospitalSelect.appendChild(option);
    }

    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);

    document.getElementById('start-time').value = yesterday.toISOString().slice(0, 16);
    document.getElementById('end-time').value = now.toISOString().slice(0, 16);

    document.getElementById('export-dialog').classList.add('show');
}

function closeExportDialog() {
    document.getElementById('export-dialog').classList.remove('show');
}

async function exportCSV() {
    const hospitalKey = document.getElementById('hospital-select').value;
    const startTime = document.getElementById('start-time').value;
    const endTime = document.getElementById('end-time').value;

    if (!hospitalKey || !startTime || !endTime) {
        alert('병원과 기간을 선택하세요.');
        return;
    }

    addLog(`📥 CSV 내보내기 시작: ${hospitalKey}`);

    try {
        const url = `${API_BASE}/api/export_csv/${hospitalKey}?start=${startTime}&end=${endTime}`;
        const response = await fetch(url);

        if (!response.ok) {
            const error = await response.json();
            alert(`CSV 내보내기 실패: ${error.error}`);
            return;
        }

        const blob = await response.blob();
        const filename = `${hospitalKey}_${startTime.replace(/[-:T]/g, '')}_${endTime.replace(/[-:T]/g, '')}.csv`;

        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);

        alert(`CSV 파일이 다운로드되었습니다.\n파일명: ${filename}`);
        closeExportDialog();
    } catch (error) {
        console.error('CSV 내보내기 오류:', error);
        alert(`CSV 내보내기 오류: ${error.message}`);
    }
}

// 초기 로드
updateDashboard();

// 5초마다 자동 갱신
setInterval(updateDashboard, 3000);
