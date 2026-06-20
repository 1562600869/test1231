const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const API = {
    async get(url) {
        const r = await fetch(url);
        return r.json();
    },
    async post(url, data) {
        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return r.json();
    },
    async put(url, data) {
        const r = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return r.json();
    },
    async del(url) {
        const r = await fetch(url, { method: 'DELETE' });
        return r.json();
    }
};

function toast(msg, type = 'ok') {
    const t = $('#toast');
    t.textContent = msg;
    t.className = 'toast show ' + type;
    setTimeout(() => t.className = 'toast', 2200);
}

function formatGrade(val) {
    return (val / 10).toFixed(1);
}

function todayStr() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function currentYearMonth() {
    const d = new Date();
    return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

function initTabs() {
    $$('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            $$('.tab-btn').forEach(b => b.classList.remove('active'));
            $$('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            $('#tab-' + btn.dataset.tab).classList.add('active');
            if (btn.dataset.tab === 'stats') loadStats();
        });
    });
}

let PLAYERS = [];

async function loadPlayers() {
    PLAYERS = await API.get('/api/players');
    const tbody = $('#players-table tbody');
    tbody.innerHTML = '';
    PLAYERS.forEach(p => {
        const tr = document.createElement('tr');
        const statusCls = p.status === '在队' ? 'status-active' : p.status === '伤停' ? 'status-injured' : 'status-gone';
        tr.innerHTML = `
            <td>${p.id}</td>
            <td>${escapeHtml(p.nickname)}</td>
            <td>${escapeHtml(p.phone || '-')}</td>
            <td>${formatGrade(p.grade)}</td>
            <td>${escapeHtml(p.position)}</td>
            <td><span class="tag ${statusCls}">${p.status}</span></td>
            <td>
                <button class="btn sm" data-edit="${p.id}">编辑</button>
                <button class="btn sm danger" data-del="${p.id}">删除</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
    tbody.querySelectorAll('[data-edit]').forEach(btn => {
        btn.addEventListener('click', () => editPlayer(parseInt(btn.dataset.edit)));
    });
    tbody.querySelectorAll('[data-del]').forEach(btn => {
        btn.addEventListener('click', () => deletePlayer(parseInt(btn.dataset.del)));
    });
    refreshPlayerCheckboxes();
    refreshStatsPlayerSelect();
}

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function editPlayer(id) {
    const p = PLAYERS.find(x => x.id === id);
    if (!p) return;
    $('#player-id').value = p.id;
    $('#player-nickname').value = p.nickname;
    $('#player-phone').value = p.phone || '';
    $('#player-grade').value = p.grade;
    $('#player-position').value = p.position;
    $('#player-status').value = p.status;
    window.scrollTo({ top: 0, behavior: 'smooth' });
    toast('已载入球员信息，可编辑后保存');
}

async function deletePlayer(id) {
    if (!confirm('确定删除该球员？相关训练/比赛出席记录也会被清除。')) return;
    await API.del('/api/players/' + id);
    await loadPlayers();
    toast('已删除球员');
}

$('#player-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = $('#player-id').value;
    const data = {
        nickname: $('#player-nickname').value.trim(),
        phone: $('#player-phone').value.trim(),
        grade: parseInt($('#player-grade').value),
        position: $('#player-position').value,
        status: $('#player-status').value
    };
    if (!data.nickname) return toast('请填写昵称', 'err');
    let resp;
    if (id) {
        resp = await API.put('/api/players/' + id, data);
    } else {
        resp = await API.post('/api/players', data);
    }
    if (resp.error) return toast('保存失败: ' + resp.error, 'err');
    resetPlayerForm();
    await loadPlayers();
    toast(id ? '球员已更新' : '球员已添加');
});

function resetPlayerForm() {
    $('#player-form').reset();
    $('#player-id').value = '';
}
$('#player-reset').addEventListener('click', resetPlayerForm);

function refreshPlayerCheckboxes() {
    ['training-attendance', 'game-roster'].forEach(cid => {
        const box = $('#' + cid);
        if (!box) return;
        box.innerHTML = PLAYERS.map(p =>
            `<label class="cb-item"><input type="checkbox" value="${p.id}"> ${escapeHtml(p.nickname)} (${formatGrade(p.grade)}·${escapeHtml(p.position)})</label>`
        ).join('');
    });
}

function refreshStatsPlayerSelect() {
    const sel = $('#stats-player-select');
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = '<option value="">请选择...</option>' +
        PLAYERS.map(p => `<option value="${p.id}">${escapeHtml(p.nickname)}</option>`).join('');
    if (cur) sel.value = cur;
}

async function loadTrainings() {
    const rows = await API.get('/api/trainings');
    const tbody = $('#trainings-table tbody');
    tbody.innerHTML = '';
    rows.forEach(t => {
        const names = t.attendance.map(a => a.nickname).join('、') || '-';
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${t.id}</td>
            <td>${t.tdate}</td>
            <td><span class="tag ttype-${t.ttype}">${t.ttype}</span></td>
            <td>${t.duration}</td>
            <td class="ellipsis" title="${escapeHtml(names)}">${escapeHtml(names)}</td>
            <td>
                <button class="btn sm" data-edit="${t.id}">编辑</button>
                <button class="btn sm danger" data-del="${t.id}">删除</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
    tbody.querySelectorAll('[data-edit]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = parseInt(btn.dataset.edit);
            const t = (await API.get('/api/trainings')).find(x => x.id === id);
            if (!t) return;
            $('#training-id').value = t.id;
            $('#training-date').value = t.tdate;
            $('#training-type').value = t.ttype;
            $('#training-duration').value = t.duration;
            $$('#training-attendance input[type=checkbox]').forEach(cb => {
                cb.checked = t.attendance.some(a => a.id === parseInt(cb.value));
            });
            window.scrollTo({ top: 0, behavior: 'smooth' });
            toast('已载入训练信息');
        });
    });
    tbody.querySelectorAll('[data-del]').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('确定删除该训练记录？')) return;
            await API.del('/api/trainings/' + btn.dataset.del);
            await loadTrainings();
            toast('已删除训练');
        });
    });
}

$('#training-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = $('#training-id').value;
    const attendance_ids = [...$$('#training-attendance input[type=checkbox]:checked')].map(cb => parseInt(cb.value));
    const data = {
        tdate: $('#training-date').value,
        ttype: $('#training-type').value,
        duration: parseInt($('#training-duration').value) || 0,
        attendance_ids
    };
    if (!data.tdate || data.duration <= 0) return toast('请填写日期和有效时长', 'err');
    let resp;
    if (id) resp = await API.put('/api/trainings/' + id, data);
    else resp = await API.post('/api/trainings', data);
    if (resp.error) return toast('保存失败: ' + resp.error, 'err');
    resetTrainingForm();
    await loadTrainings();
    toast(id ? '训练已更新' : '训练已添加');
});

function resetTrainingForm() {
    $('#training-form').reset();
    $('#training-id').value = '';
    $('#training-date').value = todayStr();
    $$('#training-attendance input[type=checkbox]').forEach(cb => cb.checked = false);
}
$('#training-reset').addEventListener('click', resetTrainingForm);

async function loadGames() {
    const rows = await API.get('/api/games');
    const tbody = $('#games-table tbody');
    tbody.innerHTML = '';
    rows.forEach(g => {
        const names = g.roster.map(r => r.nickname).join('、') || '-';
        let resultTag = '<span class="tag draw">平</span>';
        if (g.our_score > g.opp_score) resultTag = '<span class="tag win">胜</span>';
        else if (g.our_score < g.opp_score) resultTag = '<span class="tag lose">负</span>';
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${g.id}</td>
            <td>${g.gdate}</td>
            <td>${escapeHtml(g.opponent)}</td>
            <td>${g.home_away}</td>
            <td><b>${g.our_score}</b> : ${g.opp_score}</td>
            <td>${resultTag}</td>
            <td class="ellipsis" title="${escapeHtml(names)}">${escapeHtml(names)}</td>
            <td>
                <button class="btn sm" data-edit="${g.id}">编辑</button>
                <button class="btn sm danger" data-del="${g.id}">删除</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
    tbody.querySelectorAll('[data-edit]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = parseInt(btn.dataset.edit);
            const g = (await API.get('/api/games')).find(x => x.id === id);
            if (!g) return;
            $('#game-id').value = g.id;
            $('#game-opponent').value = g.opponent;
            $('#game-date').value = g.gdate;
            $('#game-home-away').value = g.home_away;
            $('#game-our-score').value = g.our_score;
            $('#game-opp-score').value = g.opp_score;
            $$('#game-roster input[type=checkbox]').forEach(cb => {
                cb.checked = g.roster.some(r => r.id === parseInt(cb.value));
            });
            window.scrollTo({ top: 0, behavior: 'smooth' });
            toast('已载入比赛信息');
        });
    });
    tbody.querySelectorAll('[data-del]').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('确定删除该比赛记录？')) return;
            await API.del('/api/games/' + btn.dataset.del);
            await loadGames();
            toast('已删除比赛');
        });
    });
}

$('#game-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = $('#game-id').value;
    const roster_ids = [...$$('#game-roster input[type=checkbox]:checked')].map(cb => parseInt(cb.value));
    const data = {
        opponent: $('#game-opponent').value.trim(),
        gdate: $('#game-date').value,
        home_away: $('#game-home-away').value,
        our_score: parseInt($('#game-our-score').value) || 0,
        opp_score: parseInt($('#game-opp-score').value) || 0,
        roster_ids
    };
    if (!data.opponent || !data.gdate) return toast('请填写对手和日期', 'err');
    let resp;
    if (id) resp = await API.put('/api/games/' + id, data);
    else resp = await API.post('/api/games', data);
    if (resp.error) return toast('保存失败: ' + resp.error, 'err');
    resetGameForm();
    await loadGames();
    toast(id ? '比赛已更新' : '比赛已添加');
});

function resetGameForm() {
    $('#game-form').reset();
    $('#game-id').value = '';
    $('#game-date').value = todayStr();
    $('#game-our-score').value = 0;
    $('#game-opp-score').value = 0;
    $$('#game-roster input[type=checkbox]').forEach(cb => cb.checked = false);
}
$('#game-reset').addEventListener('click', resetGameForm);

async function loadStats() {
    const { year, month } = currentYearMonth();

    const wl = await API.get('/api/stats/win-loss');
    const ws = $('#win-loss-stats');
    if (wl.total === 0) {
        ws.innerHTML = '<div class="stat-empty">暂无比赛记录</div>';
    } else {
        ws.innerHTML = `
            <div class="stat-card win"><div class="num">${wl.wins}</div><div class="lbl">胜场</div></div>
            <div class="stat-card lose"><div class="num">${wl.losses}</div><div class="lbl">负场</div></div>
            <div class="stat-card draw"><div class="num">${wl.draws}</div><div class="lbl">平局</div></div>
            <div class="stat-card total"><div class="num">${wl.total}</div><div class="lbl">总场次</div></div>
        `;
    }

    const tms = await API.get(`/api/stats/training-month?year=${year}&month=${month}`);
    const ts = $('#training-month-stats');
    if (tms.length === 0) {
        ts.innerHTML = `<div class="stat-empty">${year}年${month}月暂无训练</div>`;
    } else {
        let totalDur = 0, totalCnt = 0;
        const rows = tms.map(t => {
            totalDur += t.total_dur || 0;
            totalCnt += t.cnt || 0;
            return `<div class="stat-mini ttype-${t.ttype}"><b>${t.ttype}</b> ${t.cnt}次 / ${t.total_dur}分</div>`;
        }).join('');
        ts.innerHTML = rows + `<div class="stat-mini total"><b>合计</b> ${totalCnt}次 / ${totalDur}分</div>`;
    }

    loadPlayerMonthStats();
}

function loadPlayerMonthStats() {
    const sel = $('#stats-player-select');
    const out = $('#player-month-stats');
    const pid = sel.value;
    if (!pid) {
        out.innerHTML = '<div class="stat-empty">请选择球员查看本月出勤</div>';
        return;
    }
    const { year, month } = currentYearMonth();
    API.get(`/api/stats/player-month?player_id=${pid}&year=${year}&month=${month}`).then(s => {
        out.innerHTML = `
            <div class="stat-card train"><div class="num">${s.trainings}</div><div class="lbl">训练出勤</div></div>
            <div class="stat-card game"><div class="num">${s.games}</div><div class="lbl">比赛上场</div></div>
        `;
    });
}
$('#stats-player-select').addEventListener('change', loadPlayerMonthStats);

async function init() {
    initTabs();
    await loadPlayers();
    await Promise.all([loadTrainings(), loadGames()]);
    $('#training-date').value = todayStr();
    $('#game-date').value = todayStr();
}

init();
