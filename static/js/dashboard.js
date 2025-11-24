// API 베이스 URL
const API_BASE = window.location.origin;

// 타임아웃 설정 (초)
const TIMEOUT_SECONDS = 30;

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
    } catch (error) {
        console.error('데이터 갱신 오류:', error);
        addLog('❌ 데이터 갱신 오류: ' + error.message);
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

// 로그 추가
function addLog(message) {
    const now = new Date();
    const timestamp = now.toTimeString().split(' ')[0];
    const logLine = `[${timestamp}] ${message}`;

    logMessages.push(logLine);

    // 최대 100개만 유지
    if (logMessages.length > 100) {
        logMessages.shift();
    }

    const logContainer = document.getElementById('log-container');
    logContainer.innerHTML = logMessages.map((msg) => `<div class="log-line">${msg}</div>`).join('');

    // 자동 스크롤
    logContainer.scrollTop = logContainer.scrollHeight;
}

// CSV 내보내기 다이얼로그
async function showExportDialog() {
    // 병원 목록 조회
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

    // 기본 시간 설정 (어제 ~ 오늘)
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);

    document.getElementById('start-time').value = yesterday.toISOString().slice(0, 16);
    document.getElementById('end-time').value = now.toISOString().slice(0, 16);

    // 모달 표시
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
        // API 호출
        const url = `${API_BASE}/api/export_csv/${hospitalKey}?start=${startTime}&end=${endTime}`;

        // 파일 다운로드
        const response = await fetch(url);

        if (!response.ok) {
            const error = await response.json();
            alert(`CSV 내보내기 실패: ${error.error}`);
            addLog(`❌ CSV 내보내기 실패: ${error.error}`);
            return;
        }

        // Blob으로 변환
        const blob = await response.blob();

        // 파일명 생성
        const filename = `${hospitalKey}_${startTime.replace(/[-:T]/g, '')}_${endTime.replace(/[-:T]/g, '')}.csv`;

        // 다운로드 링크 생성
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);

        addLog(`✅ CSV 내보내기 완료: ${filename}`);
        alert(`CSV 파일이 다운로드되었습니다.\n파일명: ${filename}`);

        closeExportDialog();
    } catch (error) {
        console.error('CSV 내보내기 오류:', error);
        alert(`CSV 내보내기 오류: ${error.message}`);
        addLog(`❌ CSV 내보내기 오류: ${error.message}`);
    }
}

// 초기 로드
addLog('✅ 웹 대시보드 시작');
updateDashboard();

// 5초마다 자동 갱신
setInterval(updateDashboard, 5000);
