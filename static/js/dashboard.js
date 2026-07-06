// dashboard.js
// 근로복지공단 병원 전력량 모니터링 대시보드

const API_BASE = window.location.origin;
const TIMEOUT_SECONDS = 3; // 서버와 동일
const REFRESH_MS = 3000; // 실시간 갱신 주기

let monthlyChart = null; // Chart.js 인스턴스

let dailyChart = null;
let currentMonthlyData = null; // /api/monthly_usage 응답을 저장해 클릭 시 년/월을 알아냄

const REALTIME_REFRESH_MS = 5000; // 실시간 추이 갱신 주기 (5초)
let realtimeChart = null;
let realtimeIntervalId = null;

// ──────────────────────────────────────────────────
// 실시간 대시보드 갱신
// ──────────────────────────────────────────────────
async function updateDashboard() {
    try {
        const [statusRes, dataRes] = await Promise.all([
            fetch(`${API_BASE}/api/status`),
            fetch(`${API_BASE}/api/latest_data`),
        ]);

        const status = await statusRes.json();
        const latestData = await dataRes.json();

        document.getElementById('server-time').textContent = `⏰ ${status.server_time}`;

        const dbEl = document.getElementById('db-status');
        if (status.db_connected) {
            dbEl.textContent = '✅ DB 연결';
            dbEl.className = 'connected';
        } else {
            dbEl.textContent = '⚠️ DB 끊김';
            dbEl.className = 'disconnected';
        }

        updateTable(latestData);
        updateHospitalSelects(latestData);
        updateLogs();
    } catch (err) {
        console.error('대시보드 갱신 오류:', err);
    }
}

// ──────────────────────────────────────────────────
// 실시간 테이블
// ──────────────────────────────────────────────────
function updateTable(data) {
    const tbody = document.getElementById('hospital-tbody');

    if (!data || Object.keys(data).length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="no-data">등록된 병원이 없습니다</td></tr>';
        return;
    }

    const sorted = Object.entries(data).sort((a, b) => a[0].localeCompare(b[0]));

    tbody.innerHTML = sorted
        .map(([key, info], idx) => {
            const diffSec = Math.floor((Date.now() - new Date(info.timestamp)) / 1000);
            const isOffline = diffSec > TIMEOUT_SECONDS;
            const cls = isOffline ? 'offline-hospital' : '';
            const valStr = info.value.toLocaleString('ko-KR', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });
            return `
        <tr>
            <td>${idx + 1}</td>
            <td class="${cls}">${key} (${info.ip}:${info.port})</td>
            <td class="${cls}">${valStr}</td>
        </tr>`;
        })
        .join('');
}

// ──────────────────────────────────────────────────
// 병원 선택 드롭다운 동기화
// ──────────────────────────────────────────────────
function updateHospitalSelects(data) {
    const keys = Object.keys(data).sort();

    const chartSel = document.getElementById('chart-hospital-select');
    const prevChartVal = chartSel.value;
    const existingKeys = Array.from(chartSel.options)
        .map((o) => o.value)
        .filter((v) => v);
    keys.forEach((k) => {
        if (!existingKeys.includes(k)) {
            const opt = document.createElement('option');
            opt.value = k;
            opt.textContent = k;
            chartSel.appendChild(opt);
        }
    });
    if (prevChartVal) chartSel.value = prevChartVal;
}

function updateHospitalSelects(data) {
    const keys = Object.keys(data).sort();

    ['chart-hospital-select', 'realtime-hospital-select'].forEach((selectId) => {
        const sel = document.getElementById(selectId);
        const prevVal = sel.value;
        const existingKeys = Array.from(sel.options)
            .map((o) => o.value)
            .filter((v) => v);
        keys.forEach((k) => {
            if (!existingKeys.includes(k)) {
                const opt = document.createElement('option');
                opt.value = k;
                opt.textContent = k;
                sel.appendChild(opt);
            }
        });
        if (prevVal) sel.value = prevVal;
    });
}

// ──────────────────────────────────────────────────
// 시스템 로그
// ──────────────────────────────────────────────────
async function updateLogs() {
    try {
        const res = await fetch(`${API_BASE}/api/logs`);
        const logs = await res.json();

        document.getElementById('log-container').innerHTML = logs
            .slice(-10)
            .reverse()
            .map((l) => `<div class="log-line">[${l.timestamp}] 💾 ${l.message}</div>`)
            .join('');
    } catch (err) {
        console.error('로그 갱신 오류:', err);
    }
}

// ──────────────────────────────────────────────────
// 월별 차트
// ──────────────────────────────────────────────────
async function loadMonthlyChart() {
    const hospitalKey = document.getElementById('chart-hospital-select').value;
    const noDataEl = document.getElementById('chart-no-data');
    const statsEl = document.getElementById('monthly-stats');

    if (!hospitalKey) {
        noDataEl.textContent = '병원을 선택하면 차트가 표시됩니다';
        noDataEl.style.display = 'flex';
        statsEl.style.display = 'none';
        if (monthlyChart) {
            monthlyChart.destroy();
            monthlyChart = null;
        }
        return;
    }

    noDataEl.textContent = '데이터 불러오는 중...';
    noDataEl.style.display = 'flex';

    try {
        const res = await fetch(`${API_BASE}/api/monthly_usage/${hospitalKey}`);
        const json = await res.json();

        if (json.error) {
            noDataEl.textContent = `데이터 없음: ${json.error}`;
            statsEl.style.display = 'none';
            return;
        }

        noDataEl.style.display = 'none';
        currentMonthlyData = json;
        renderMonthlyChart(json);
        renderMonthlyStats(json);
        statsEl.style.display = 'flex';
    } catch (err) {
        noDataEl.textContent = '차트 로드 실패: ' + err.message;
        console.error(err);
    }
}

function renderMonthlyChart(data) {
    const labels = data.months.map((m) => {
        const [y, mo] = m.split('-');
        return `${y.slice(2)}년 ${parseInt(mo)}월`;
    });

    const currentDataset = {
        label: '당월 사용량 (kWh)',
        data: data.usage,
        backgroundColor: data.usage.map((v, i) => {
            return i === data.usage.length - 1 ? 'rgba(0, 120, 215, 0.9)' : 'rgba(0, 120, 215, 0.55)';
        }),
        borderColor: 'rgba(0, 120, 215, 1)',
        borderWidth: 1,
        borderRadius: 4,
        order: 2,
    };

    const prevDataset = {
        label: '전년 동월 (kWh)',
        data: data.prev_year_usage,
        type: 'line',
        borderColor: 'rgba(229, 57, 53, 0.8)',
        backgroundColor: 'transparent',
        borderWidth: 2,
        borderDash: [6, 3],
        pointBackgroundColor: 'rgba(229, 57, 53, 0.9)',
        pointRadius: 4,
        tension: 0.3,
        spanGaps: true,
        order: 1,
    };

    if (monthlyChart) monthlyChart.destroy();

    const ctx = document.getElementById('monthly-chart').getContext('2d');
    monthlyChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [currentDataset, prevDataset] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            onClick: (evt, elements, chart) => {
                const points = chart.getElementsAtEventForMode(evt, 'nearest', { intersect: true }, true);
                if (!points.length) return;
                const idx = points[0].index;
                const monthStr = data.months[idx];
                if (currentDataset.data[idx] === null || currentDataset.data[idx] === undefined) return;
                const [year, month] = monthStr.split('-').map(Number);
                loadDailyChart(monthStr, year, month);
            },
            onHover: (evt, elements) => {
                evt.native.target.style.cursor = elements.length ? 'pointer' : 'default';
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { font: { size: 12 }, padding: 16 },
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const val = ctx.parsed.y;
                            if (val === null || val === undefined) return `${ctx.dataset.label}: 데이터 없음`;
                            return `${ctx.dataset.label}: ${val.toLocaleString('ko-KR', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                            })} kWh`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 11 } },
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'kWh', font: { size: 12 } },
                    ticks: {
                        font: { size: 11 },
                        callback: (v) => v.toLocaleString('ko-KR'),
                    },
                },
            },
        },
    });
}

function renderMonthlyStats(data) {
    const usage = data.usage.filter((v) => v !== null && v !== undefined);
    const prevUsage = data.prev_year_usage.filter((v) => v !== null && v !== undefined);

    const lastUsage = [...data.usage].reverse().find((v) => v !== null && v !== undefined);

    const nonNull = data.usage.filter((v) => v !== null && v !== undefined);
    const prevMonth = nonNull.length >= 2 ? nonNull[nonNull.length - 2] : null;

    const last3 = nonNull.slice(-3);
    const avg3 = last3.length ? last3.reduce((a, b) => a + b, 0) / last3.length : null;

    const max12 = usage.length ? Math.max(...usage) : null;

    let diffHtml = '-';
    if (lastUsage !== undefined && prevMonth !== null) {
        const diff = lastUsage - prevMonth;
        const diffPct = prevMonth ? ((diff / prevMonth) * 100).toFixed(1) : null;
        const sign = diff >= 0 ? '▲' : '▼';
        const color = diff >= 0 ? '#c80000' : '#1565c0';
        diffHtml = `<span style="color:${color}">${sign} ${Math.abs(diff).toLocaleString('ko-KR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })} kWh${diffPct !== null ? ` (${Math.abs(diffPct)}%)` : ''}</span>`;
    }

    document.getElementById('stat-last').textContent =
        lastUsage !== undefined
            ? `${lastUsage.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kWh`
            : '-';
    document.getElementById('stat-avg3').textContent =
        avg3 !== null
            ? `${avg3.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kWh`
            : '-';
    document.getElementById('stat-max').textContent =
        max12 !== null
            ? `${max12.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kWh`
            : '-';
    document.getElementById('stat-diff').innerHTML = diffHtml;
}

// ──────────────────────────────────────────────────
// 일별 드릴다운 차트
// ──────────────────────────────────────────────────
async function loadDailyChart(monthStr, year, month) {
    const hospitalKey = document.getElementById('chart-hospital-select').value;
    const section = document.getElementById('daily-section');
    const titleEl = document.getElementById('daily-title');

    section.style.display = 'block';
    titleEl.textContent = `${year}년 ${month}월 일별 사용량 불러오는 중...`;

    try {
        const res = await fetch(`${API_BASE}/api/daily_usage/${hospitalKey}/${year}/${month}`);
        const json = await res.json();

        if (json.error) {
            titleEl.textContent = `데이터 없음: ${json.error}`;
            return;
        }

        titleEl.textContent = `${year}년 ${month}월 일별 사용량 (1일~${json.days[json.days.length - 1]}일)`;
        renderDailyChart(json);
        renderDailyStats(json);

        section.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (err) {
        titleEl.textContent = '일별 데이터 로드 실패: ' + err.message;
        console.error(err);
    }
}

function renderDailyChart(json) {
    const labels = json.days.map((d) => `${d}일`);

    if (dailyChart) dailyChart.destroy();

    const ctx = document.getElementById('daily-chart').getContext('2d');
    dailyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: '일별 사용량 (kWh)',
                    data: json.usage,
                    backgroundColor: 'rgba(93, 202, 165, 0.75)',
                    borderRadius: 3,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const val = ctx.parsed.y;
                            if (val === null || val === undefined) return '데이터 없음';
                            return `${val.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kWh`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 10 }, autoSkip: true, maxTicksLimit: 16 },
                },
                y: {
                    beginAtZero: true,
                    ticks: { font: { size: 11 }, callback: (v) => v.toLocaleString('ko-KR') },
                },
            },
        },
    });
}

function renderDailyStats(json) {
    const valid = json.usage.map((v, i) => ({ v, day: json.days[i] })).filter((x) => x.v !== null && x.v !== undefined);

    if (!valid.length) {
        document.getElementById('daily-avg').textContent = '-';
        document.getElementById('daily-max').textContent = '-';
        document.getElementById('daily-min').textContent = '-';
        return;
    }

    const avg = valid.reduce((a, b) => a + b.v, 0) / valid.length;
    const max = valid.reduce((a, b) => (b.v > a.v ? b : a));
    const min = valid.reduce((a, b) => (b.v < a.v ? b : a));

    const fmt = (v) => v.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' kWh';

    document.getElementById('daily-avg').textContent = fmt(avg);
    document.getElementById('daily-max').textContent = `${max.day}일 (${fmt(max.v)})`;
    document.getElementById('daily-min').textContent = `${min.day}일 (${fmt(min.v)})`;
}

function closeDailySection() {
    document.getElementById('daily-section').style.display = 'none';
    if (dailyChart) {
        dailyChart.destroy();
        dailyChart = null;
    }
}

// ──────────────────────────────────────────────────
// 실시간 전력량 추이
// ──────────────────────────────────────────────────
function onRealtimeControlsChange() {
    // 병원 또는 범위가 바뀌면 기존 폴링을 멈추고 새로 시작
    if (realtimeIntervalId) {
        clearInterval(realtimeIntervalId);
        realtimeIntervalId = null;
    }

    loadRealtimeChart();

    const hospitalKey = document.getElementById('realtime-hospital-select').value;
    if (hospitalKey) {
        realtimeIntervalId = setInterval(loadRealtimeChart, REALTIME_REFRESH_MS);
    }
}

async function loadRealtimeChart() {
    const hospitalKey = document.getElementById('realtime-hospital-select').value;
    const minutes = document.getElementById('realtime-range-select').value;
    const noDataEl = document.getElementById('realtime-no-data');

    if (!hospitalKey) {
        noDataEl.textContent = '병원을 선택하면 실시간 추이가 표시됩니다';
        noDataEl.style.display = 'flex';
        if (realtimeChart) {
            realtimeChart.destroy();
            realtimeChart = null;
        }
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/recent_data/${hospitalKey}?minutes=${minutes}`);
        const json = await res.json();

        if (json.error) {
            noDataEl.textContent = `데이터 없음: ${json.error}`;
            noDataEl.style.display = 'flex';
            return;
        }

        if (!json.points || json.points.length === 0) {
            noDataEl.textContent = '최근 데이터가 없습니다';
            noDataEl.style.display = 'flex';
            if (realtimeChart) {
                realtimeChart.destroy();
                realtimeChart = null;
            }
            return;
        }

        noDataEl.style.display = 'none';
        renderRealtimeChart(json.points);
    } catch (err) {
        noDataEl.textContent = '실시간 데이터 로드 실패: ' + err.message;
        noDataEl.style.display = 'flex';
        console.error(err);
    }
}

function renderRealtimeChart(points) {
    const labels = points.map((p) => p.timestamp.slice(11)); // "HH:MM:SS"만 추출
    const values = points.map((p) => p.value);

    const data = {
        labels,
        datasets: [
            {
                label: '전력량 (kWh)',
                data: values,
                borderColor: 'rgba(0, 120, 215, 1)',
                backgroundColor: 'rgba(0, 120, 215, 0.08)',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.2,
                fill: true,
            },
        ],
    };

    if (realtimeChart) {
        // [성능] 매번 destroy/create하지 않고 데이터만 교체 후 update
        // → 5초마다 다시 그리는 실시간 차트라 깜빡임을 줄이기 위함
        realtimeChart.data = data;
        realtimeChart.update();
        return;
    }

    const ctx = document.getElementById('realtime-chart').getContext('2d');
    realtimeChart = new Chart(ctx, {
        type: 'line',
        data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) =>
                            `${ctx.parsed.y.toLocaleString('ko-KR', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                            })} kWh`,
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 10 }, autoSkip: true, maxRotation: 0 },
                },
                y: {
                    ticks: { font: { size: 11 }, callback: (v) => v.toLocaleString('ko-KR') },
                },
            },
        },
    });
}

// ──────────────────────────────────────────────────
// CSV 내보내기 다이얼로그
// ──────────────────────────────────────────────────
async function showExportDialog() {
    const res = await fetch(`${API_BASE}/api/latest_data`);
    const data = await res.json();

    const sel = document.getElementById('hospital-select');
    sel.innerHTML = '';

    if (!data || Object.keys(data).length === 0) {
        alert('등록된 병원이 없습니다.');
        return;
    }

    Object.keys(data)
        .sort()
        .forEach((k) => {
            const opt = document.createElement('option');
            opt.value = k;
            opt.textContent = k;
            sel.appendChild(opt);
        });

    const now = new Date();
    const yesterday = new Date(now.getTime() - 86400000);
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

    try {
        const url = `${API_BASE}/api/export_csv/${hospitalKey}?start=${startTime}&end=${endTime}`;
        const response = await fetch(url);

        if (!response.ok) {
            const err = await response.json();
            alert(`CSV 내보내기 실패: ${err.error}`);
            return;
        }

        const blob = await response.blob();
        const filename = `${hospitalKey}_${startTime.replace(/[-:T]/g, '')}_${endTime.replace(/[-:T]/g, '')}.csv`;
        const dlUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = dlUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(dlUrl);

        alert(`다운로드 완료: ${filename}`);
        closeExportDialog();
    } catch (err) {
        alert(`CSV 내보내기 오류: ${err.message}`);
    }
}

// ──────────────────────────────────────────────────
// 초기화
// ──────────────────────────────────────────────────
updateDashboard();
setInterval(updateDashboard, REFRESH_MS);
