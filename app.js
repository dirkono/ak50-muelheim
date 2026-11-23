// =============================================================================
// GV NRW AK 50 Herren - Web-App Logik (app.js)
// Strikte CSP-Konformität: Keine Inline-Scripts, keine Inline-Event-Handler
// =============================================================================

// 1. Tailwind CSS Konfiguration (GC Mülheim Vereinsblau #006eb7)
window.tailwind = window.tailwind || {};
window.tailwind.config = {
    darkMode: 'media',
    theme: {
        extend: {
            colors: {
                blue: {
                    50: '#f0f7fc',
                    100: '#e0eff9',
                    200: '#c2d0ed',
                    300: '#8fc1e8',
                    400: '#4fa3dc',
                    500: '#1b88ce',
                    600: '#006eb7',
                    700: '#006eb7',
                    800: '#00558f',
                    900: '#003e69',
                    950: '#00223b',
                    DEFAULT: '#006eb7',
                },
                gcmh: {
                    50: '#f0f7fc',
                    100: '#e0eff9',
                    200: '#c2d0ed',
                    300: '#8fc1e8',
                    400: '#4fa3dc',
                    500: '#1b88ce',
                    600: '#006eb7',
                    700: '#006eb7',
                    800: '#00558f',
                    900: '#003e69',
                    950: '#00223b',
                    DEFAULT: '#006eb7',
                },
                sky: {
                    50: '#f0f7fc',
                    100: '#e0eff9',
                    200: '#c2d0ed',
                    300: '#8fc1e8',
                    400: '#4fa3dc',
                    500: '#1b88ce',
                    600: '#006eb7',
                    700: '#006eb7',
                    800: '#00558f',
                    900: '#003e69',
                    950: '#00223b',
                    DEFAULT: '#006eb7',
                }
            }
        }
    }
};

// 2. Daten & Initialer Zustand
let GVNRW_DATA = {};
try {
    const dataEl = document.getElementById('golf-data');
    if (dataEl && dataEl.textContent) {
        GVNRW_DATA = JSON.parse(dataEl.textContent);
    }
} catch (err) {
    console.error('[App] Fehler beim Parsen von #golf-data:', err);
}

const urlParams = new URLSearchParams(window.location.search);
let currentYear = urlParams.get('year') || localStorage.getItem('gvnrw_year') || '2026';
let currentTeam = urlParams.get('team') || localStorage.getItem('gvnrw_team') || '1';
let currentModalTab = 'teams';
let allTableExpanded = false;

// 3. UI-Hilfsfunktionen
function showToast(message, icon = '📋') {
    const toast = document.getElementById('toastNotification');
    const msgEl = document.getElementById('toastMessage');
    const iconEl = document.getElementById('toastIcon');
    if (!toast) return;
    if (msgEl) msgEl.innerText = message;
    if (iconEl) iconEl.innerText = icon;
    toast.classList.remove('opacity-0', 'translate-y-3');
    toast.classList.add('opacity-100', 'translate-y-0');
    setTimeout(() => {
        toast.classList.remove('opacity-100', 'translate-y-0');
        toast.classList.add('opacity-0', 'translate-y-3');
    }, 2500);
}

function getShareUrl() {
    if (window.location.protocol.startsWith('http')) {
        const u = new URL(window.location.href);
        u.searchParams.set('year', currentYear);
        u.searchParams.set('team', currentTeam);
        return u.toString();
    }
    const officialLinks = {
        '2024': { '1': 'https://gvnrw.liga.golf/3324/3325?year=2024', '2': 'https://gvnrw.liga.golf/3324/3359?year=2024' },
        '2025': { '1': 'https://gvnrw.liga.golf/3581/3582?year=2025', '2': 'https://gvnrw.liga.golf/3581/3619?year=2025' },
        '2026': { '1': 'https://gvnrw.liga.golf/3844/3845?year=2026', '2': 'https://gvnrw.liga.golf/3844/3882?year=2026' },
        '2027': { '1': 'https://gvnrw.liga.golf/4009/4110?year=2027', '2': 'https://gvnrw.liga.golf/4009/4150?year=2027' },
    };
    if (officialLinks[currentYear] && officialLinks[currentYear][currentTeam]) {
        return officialLinks[currentYear][currentTeam];
    }
    return 'https://gvnrw.liga.golf/';
}

function openShareModal() {
    const modal = document.getElementById('shareModal');
    const subTitle = document.getElementById('shareModalSubtitle');
    const input = document.getElementById('shareUrlInput');
    const url = getShareUrl();
    if (subTitle) subTitle.innerText = `⛳ GC Mülheim ${currentTeam} • Saison ${currentYear}`;
    if (input) input.value = url;

    const copyBtn = document.getElementById('copyShareBtn');
    if (copyBtn) copyBtn.innerHTML = '<span>Kopieren</span>';

    const sysBtn = document.getElementById('systemShareBtn');
    if (sysBtn) {
        const canSys = !!(navigator.share && window.isSecureContext);
        sysBtn.style.display = canSys ? 'flex' : 'none';
    }

    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function closeShareModal() {
    const modal = document.getElementById('shareModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

function closeShareModalOnBackdrop(event) {
    if (event.target.id === 'shareModal') {
        closeShareModal();
    }
}

function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text);
    }
    return new Promise((resolve, reject) => {
        try {
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);
            if (successful) resolve();
            else reject(new Error('Kopieren fehlgeschlagen'));
        } catch (err) {
            reject(err);
        }
    });
}

function copyShareUrl() {
    const url = getShareUrl();
    copyTextToClipboard(url).then(() => {
        const btn = document.getElementById('copyShareBtn');
        if (btn) btn.innerHTML = '<span>Kopiert! ✓</span>';
        showToast('Link erfolgreich kopiert!', '🔗');
        setTimeout(() => {
            if (btn) btn.innerHTML = '<span>Kopieren</span>';
        }, 2000);
    }).catch(() => {
        showToast('Kopieren fehlgeschlagen', '⚠️');
    });
}

function shareViaWhatsApp() {
    const url = getShareUrl();
    const text = encodeURIComponent(`AK 50 Herren GC Mülheim ${currentTeam} (${currentYear}): ${url}`);
    window.open(`https://api.whatsapp.com/send?text=${text}`, '_blank');
}

function shareViaEmail() {
    const url = getShareUrl();
    const subject = encodeURIComponent(`AK 50 Herren Ergebnisse - GC Mülheim ${currentTeam} (${currentYear})`);
    const body = encodeURIComponent(`Hallo,

hier sind die aktuellen Ergebnisse und Spieltage der AK 50 Herren (GC Mülheim ${currentTeam}, Saison ${currentYear}):

${url}

Sportliche Grüße`);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
}

function triggerSystemShare() {
    if (navigator.share) {
        navigator.share({
            title: `AK 50 Herren - GC Mülheim ${currentTeam} (${currentYear})`,
            text: `Ergebnisse, Tabellen und Spieltage der AK 50 Herren des GC Mülheim an der Ruhr (${currentYear}):`,
            url: getShareUrl(),
        }).catch((err) => {
            if (err.name !== 'AbortError') {
                copyShareUrl();
            }
        });
    } else {
        copyShareUrl();
    }
}

function setYear(year, render = true) {
    currentYear = year;
    localStorage.setItem('gvnrw_year', year);
    document.querySelectorAll('#yearSelector button').forEach(b => {
        const isActive = b.dataset.year === year;
        b.className = isActive
            ? 'py-1.5 text-xs font-semibold rounded-md bg-white dark:bg-slate-800 text-blue-700 dark:text-sky-400 shadow-2xs font-bold transition-all text-center'
            : 'py-1.5 text-xs font-semibold rounded-md text-slate-600 dark:text-slate-300 transition-all text-center hover:text-slate-900 dark:hover:text-white';
    });
    if (render) renderView();
}

function setTeam(team, render = true) {
    currentTeam = team;
    localStorage.setItem('gvnrw_team', team);
    document.querySelectorAll('#teamSelector button').forEach(b => {
        const isActive = b.dataset.team === team;
        b.className = isActive
            ? 'py-1.5 px-2.5 text-xs rounded-md bg-white dark:bg-slate-800 text-blue-700 dark:text-sky-400 shadow-2xs font-bold transition-all flex items-center justify-center gap-1.5'
            : 'py-1.5 px-2.5 text-xs rounded-md text-slate-600 dark:text-slate-300 font-semibold transition-all flex items-center justify-center gap-1.5 hover:text-slate-900 dark:hover:text-white';
    });
    if (render) renderView();
}

function toggleClubMatchdays(idx) {
    const el = document.getElementById(`clubMatchdays-${idx}`);
    const arrow = document.getElementById(`clubArrow-${idx}`);
    if (!el) return;
    const isHidden = el.classList.contains('hidden');
    el.classList.toggle('hidden', !isHidden);
    if (arrow) arrow.innerText = isHidden ? '▴' : '▾';
}

function toggleAllTableMatchdays() {
    allTableExpanded = !allTableExpanded;
    document.querySelectorAll('[id^="clubMatchdays-"]').forEach(el => {
        el.classList.toggle('hidden', !allTableExpanded);
    });
    document.querySelectorAll('[id^="clubArrow-"]').forEach(arrow => {
        arrow.innerText = allTableExpanded ? '▴' : '▾';
    });
    const btn = document.getElementById('toggleAllBtn');
    if (btn) {
        btn.innerHTML = allTableExpanded
            ? '<span>Verbergen</span> <span>▴</span>'
            : '<span>Spieltage</span> <span>▾</span>';
    }
}

function renderView() {
    const yearData = GVNRW_DATA[currentYear] || {};
    const groupData = yearData[currentTeam];

    if (!groupData) {
        document.getElementById('leagueGroupTitle').innerText = 'Keine Daten';
        document.getElementById('standingsTableBody').innerHTML = '<tr><td colspan="4" class="py-6 text-center text-slate-400">Keine Daten für dieses Jahr verfügbar.</td></tr>';
        document.getElementById('matchdaysGrid').innerHTML = '';
        return;
    }

    const groupName = groupData.group_name || 'Gruppe';
    document.getElementById('leagueGroupTitle').innerText = groupName + ' (' + currentYear + ')';
    document.getElementById('subHeaderDesc').innerText = 'AK 50 Herren ' + currentYear + ' • GC Mülheim ' + currentTeam;

    const teams = groupData.teams || [];
    const muelheimTeam = teams.find(t => t.club.toLowerCase().includes('mülheim'));
    if (muelheimTeam) {
        document.getElementById('myRankBadge').innerText = 'Rang #' + muelheimTeam.rank;
        document.getElementById('seasonPointsTag').innerText = muelheimTeam.points + ' Punkte';
    } else {
        document.getElementById('myRankBadge').innerText = '-';
        document.getElementById('seasonPointsTag').innerText = '';
    }

    let tableHtml = '';
    teams.forEach((t, idx) => {
        const isMuelheim = t.club.toLowerCase().includes('mülheim');
        const rowBg = isMuelheim
            ? 'bg-blue-50/90 dark:bg-blue-950/60 font-bold border-l-4 border-blue-600'
            : (idx % 2 === 0 ? 'bg-white dark:bg-slate-800' : 'bg-slate-50/75 dark:bg-slate-800/40');

        let rankBadge = `<span class="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200">${t.rank}</span>`;
        if (t.rank === '1') rankBadge = `<span class="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">1</span>`;
        if (t.rank === '2') rankBadge = `<span class="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-slate-200 text-slate-800 border border-slate-300">2</span>`;
        if (t.rank === '3') rankBadge = `<span class="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-orange-100 text-orange-900 border border-orange-300">3</span>`;

        let matchdaysButton = '';
        let matchdaysSummary = '';
        if (t.matchdays && Object.keys(t.matchdays).length > 0) {
            const mdEntries = Object.entries(t.matchdays)
                .filter(([k, v]) => v)
                .map(([k, v]) => {
                    const isNachholer = v.includes('[Nachholer]');
                    const cleanVal = v.replace(' [Nachholer]', '');
                    const badgeCls = isNachholer
                        ? 'bg-blue-600 text-white font-bold shadow-xs'
                        : 'bg-slate-100 text-slate-700 dark:bg-slate-700/60 dark:text-slate-300 border border-slate-200 dark:border-slate-700';
                    const label = isNachholer ? `${k} (Nachholer)` : k;
                    return `<span class="inline-block px-1.5 py-0.2 rounded text-[10px] ${badgeCls}">${label}: <strong>${cleanVal}</strong></span>`;
                });
            if (mdEntries.length > 0) {
                matchdaysButton = `
                <button type="button" data-action="toggle-club" data-club-idx="${idx}" class="inline-flex items-center gap-0.5 text-[10px] text-slate-400 hover:text-blue-700 dark:hover:text-sky-400 px-1 py-0.2 rounded hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors ml-1.5">
                    <span>Spieltage</span> <span id="clubArrow-${idx}">▾</span>
                </button>
                `;
                matchdaysSummary = `<div id="clubMatchdays-${idx}" class="hidden mt-1 flex flex-wrap gap-1">${mdEntries.join(' ')}</div>`;
            }
        }

        tableHtml += `
        <tr class="${rowBg} hover:bg-blue-50/50 dark:hover:bg-slate-700/50 transition-colors cursor-pointer" data-club-idx="${idx}">
            <td class="py-2 px-2 text-center align-middle">${rankBadge}</td>
            <td class="py-2 px-2.5">
                <div class="font-medium text-slate-900 dark:text-slate-100 flex items-center justify-between">
                    <span class="flex items-center gap-1">${t.club} ${isMuelheim ? '<span class="text-xs">🏌️‍♂️</span>' : ''}</span>
                    ${matchdaysButton}
                </div>
                ${matchdaysSummary}
            </td>
            <td class="py-2 px-2.5 text-right font-bold text-blue-700 dark:text-sky-400 align-middle text-xs sm:text-sm">${t.points || '-'}</td>
            <td class="py-2 px-2.5 text-right text-slate-500 dark:text-slate-400 font-mono align-middle text-xs">${t.avg_cr || '-'}</td>
        </tr>
        `;
    });
    document.getElementById('standingsTableBody').innerHTML = tableHtml;

    const matchdaysDetails = groupData.matchdays_details || {};
    const canceledList = Object.keys(matchdaysDetails).filter(k => matchdaysDetails[k].is_canceled);
    const rescheduledList = Object.keys(matchdaysDetails).filter(k => matchdaysDetails[k].is_rescheduled);

    let noticeHtml = '';
    if (canceledList.length > 0 || rescheduledList.length > 0) {
        let noteText = '';
        if (canceledList.length > 0 && rescheduledList.length > 0) {
            noteText = `<strong>Spielplan-Besonderheit (${groupName}):</strong> Der <strong>${canceledList.join(', ')}</strong> fiel aus und wurde im Nachholtermin (<strong>${rescheduledList.join(', ')}</strong>) ausgetragen. Die Punkte fließen vollständig in das offizielle Endergebnis ein.`;
        } else if (canceledList.length > 0) {
            noteText = `<strong>Spielplan-Besonderheit (${groupName}):</strong> Folgende Spieltage fielen aus: <strong>${canceledList.join(', ')}</strong>.`;
        } else {
            noteText = `<strong>Spielplan-Besonderheit (${groupName}):</strong> Enthält nachgeholte Spieltage: <strong>${rescheduledList.join(', ')}</strong>. Alle Punkte fließen vollständig in das Endergebnis ein.`;
        }
        noticeHtml = `
        <div class="px-4 py-2.5 bg-amber-50 dark:bg-amber-950/40 border-t border-amber-200/70 dark:border-amber-800/50 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2">
            <span class="text-base leading-none">ℹ️</span>
            <div>${noteText}</div>
        </div>
        `;
    }
    document.getElementById('tableNoticeContainer').innerHTML = noticeHtml;

    let gridHtml = '';
    const dayKeys = Object.keys(matchdaysDetails).sort((a,b) => {
        const dateA = matchdaysDetails[a].date || '';
        const dateB = matchdaysDetails[b].date || '';
        if (dateA && dateB) {
            return dateA.localeCompare(dateB);
        }
        const idxA = (groupData.headers || []).indexOf(a);
        const idxB = (groupData.headers || []).indexOf(b);
        if (idxA >= 0 && idxB >= 0) return idxA - idxB;
        return (parseInt(a) || 0) - (parseInt(b) || 0);
    });

    dayKeys.forEach(dayKey => {
        const d = matchdaysDetails[dayKey];
        const myResult = (d.team_results || []).find(r => r.team_name.toLowerCase().includes('mülheim'));
        const scoreText = myResult ? (myResult.score ? myResult.score + ' (' + (myResult.points || '0') + ' Pkt)' : myResult.points + ' Pkt') : '-';
        let cardClass = 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 shadow-xs hover:border-blue-500';
        let dayTitleDisplay = d.day_name;
        let dateDisplay = `<span class="text-[11px] text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-700/60 px-2 py-0.5 rounded-md font-mono">${d.date || 'Termin folgt'}</span>`;

        if (d.is_canceled && d.linked_rescheduled_day) {
            dayTitleDisplay = `<div class="flex items-center gap-2 flex-wrap">
                <span class="font-extrabold text-sm text-slate-900 dark:text-white">${d.day_name}</span>
                <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-600 text-white shadow-xs">🔄 Nachholer am 19.09.</span>
            </div>`;
            dateDisplay = `<div class="text-right">
                <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300 border border-amber-300">Urspr. 02.05. ausgefallen</span>
                <div class="text-xs text-blue-600 dark:text-blue-400 font-bold font-mono mt-0.5">gespielt 19.09.</div>
            </div>`;
            cardClass = 'bg-blue-50/40 dark:bg-blue-950/20 border-2 border-blue-500 shadow-xs hover:border-blue-600';
        } else if (d.is_canceled) {
            dayTitleDisplay = `<span class="font-bold text-sm text-slate-900 dark:text-white">${d.day_name}</span>`;
            dateDisplay = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300 border border-amber-300">Ausgefallen</span> <span class="text-[11px] text-slate-400 line-through font-mono ml-1">${d.date || ''}</span>`;
            cardClass = 'bg-amber-50/40 dark:bg-amber-950/20 border-dashed border-amber-300 dark:border-amber-700/60 opacity-85 hover:border-amber-400';
        } else if (d.is_rescheduled) {
            const canceledLabel = d.linked_canceled_day ? ` (Nachholer für ${d.linked_canceled_day})` : '';
            dayTitleDisplay = `<div class="flex items-center gap-2 flex-wrap">
                <span class="font-extrabold text-sm text-slate-900 dark:text-white">${d.day_name}${canceledLabel}</span>
                <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-600 text-white shadow-xs">🔄 Nachholspieltag</span>
            </div>`;
            dateDisplay = `<span class="text-[11px] text-blue-700 dark:text-blue-300 bg-blue-100 dark:bg-blue-950/80 px-2 py-0.5 rounded-md font-mono font-bold border border-blue-300 dark:border-blue-700">${d.date}</span>`;
            cardClass = 'bg-white dark:bg-slate-800 border-2 border-blue-400 dark:border-blue-600 shadow-xs hover:border-blue-500';
        }

        const venueText = d.venue ? d.venue : (d.is_canceled ? 'Spieltag fand nicht statt' : 'Spielort offen');

        gridHtml += `
        <div class="${cardClass} rounded-xl p-3.5 border transition-all cursor-pointer flex flex-col justify-between active:scale-[0.98]" data-day-key="${dayKey}">
            <div>
                <div class="flex justify-between items-start mb-1 flex-wrap gap-1">
                    <div>${dayTitleDisplay}</div>
                    <div>${dateDisplay}</div>
                </div>
                <p class="text-xs text-slate-500 dark:text-slate-400 truncate mb-3">${venueText}</p>
            </div>
            <div class="flex justify-between items-center pt-2.5 border-t border-slate-100 dark:border-slate-700">
                <span class="text-xs font-bold text-blue-700 dark:text-sky-400">${scoreText}</span>
                <span class="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1 font-medium">Details ➜</span>
            </div>
        </div>
        `;
    });

    if (dayKeys.length === 0) {
        gridHtml = '<p class="col-span-2 text-center py-6 text-xs text-slate-400">Keine Spieltage für diese Gruppe hinterlegt.</p>';
    }
    document.getElementById('matchdaysGrid').innerHTML = gridHtml;
}

function openMatchdayModal(dayKey) {
    const groupData = GVNRW_DATA[currentYear]?.[currentTeam];
    const d = groupData?.matchdays_details?.[dayKey];
    if (!d) return;

    document.getElementById('modalDayTitle').innerText = d.day_name;
    document.getElementById('modalDayDate').innerText = d.date ? 'Datum: ' + d.date : 'Termin noch offen';
    document.getElementById('modalVenueText').innerText = d.venue || (d.is_canceled ? 'Spieltag ausgefallen' : 'Nicht spezifiziert');

    if (d.tee_info) {
        document.getElementById('modalTeeRow').style.display = 'block';
        document.getElementById('modalTeeText').innerText = d.tee_info;
    } else {
        document.getElementById('modalTeeRow').style.display = 'none';
    }

    const bannerBox = document.getElementById('modalBannerContainer');
    if (d.is_canceled && d.linked_rescheduled_day) {
        bannerBox.innerHTML = `
        <div class="mb-3 p-3 rounded-xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-xs text-blue-900 dark:text-blue-200">
            <div class="font-extrabold flex items-center gap-1 mb-1">
                <span>🔄</span> <span>Spieltag wurde nachgeholt!</span>
            </div>
            <p>Dieser Spieltag war ursprünglich für den 02.05.2026 angesetzt, musste jedoch wetterbedingt abgesagt werden. Er wurde am <strong>19.09.2026</strong> im <strong>GC Essen-Heidhausen</strong> nachgeholt. Die hier angezeigten Ergebnisse und Punkte stammen von diesem Nachholtermin.</p>
        </div>
        `;
    } else if (d.is_canceled) {
        bannerBox.innerHTML = `
        <div class="mb-3 p-3 rounded-xl bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800 text-xs text-amber-900 dark:text-amber-200">
            <div class="font-bold flex items-center gap-1 mb-1">
                <span>⚠️</span> <span>Spieltag ausgefallen / entfallen</span>
            </div>
            <p>Dieser Spieltag wurde nicht ausgetragen.</p>
        </div>
        `;
    } else {
        bannerBox.innerHTML = '';
    }

    // Tab 1: Teams
    let teamHtml = '';
    const results = d.team_results || [];
    results.forEach(r => {
        const isMuelheim = r.team_name.toLowerCase().includes('mülheim');
        const rowBg = isMuelheim ? 'bg-blue-50/90 dark:bg-blue-950/60 font-bold' : '';
        const rank = r.rank ? `#${r.rank}` : '-';
        teamHtml += `
        <tr class="${rowBg}">
            <td class="py-2 px-2.5 text-center font-semibold text-slate-500">${rank}</td>
            <td class="py-2 px-2.5 font-medium text-slate-900 dark:text-white flex items-center gap-1.5">
                ${r.team_name} ${isMuelheim ? '<span class="text-xs">🏌️‍♂️</span>' : ''}
            </td>
            <td class="py-2 px-2.5 text-right font-mono text-slate-700 dark:text-slate-300">${r.score || '-'}</td>
            <td class="py-2 px-2.5 text-right font-bold text-blue-700 dark:text-sky-400">${r.points ? r.points + ' Pkt' : '-'}</td>
        </tr>
        `;
    });
    if (results.length === 0) {
        teamHtml = '<tr><td colspan="4" class="py-6 text-center text-slate-400">Keine Mannschaftsergebnisse für diesen Spieltag.</td></tr>';
    }
    document.getElementById('modalTeamResultsBody').innerHTML = teamHtml;

    // Tab 2: Players
    let playerHtml = '';
    const players = d.players || [];
    players.forEach(p => {
        const isStreich = p.is_cutoff;
        const cardBg = isStreich
            ? 'bg-slate-50/70 dark:bg-slate-800/40 border-dashed border-slate-300 dark:border-slate-700 opacity-75'
            : 'bg-white dark:bg-slate-800/90 border-slate-200 dark:border-slate-700 shadow-2xs';

        let holeByHole = '';
        if (p.pars && p.pars.length >= 21 && p.scores && p.scores.length >= 21) {
            function formatHole(score, par) {
                if (score == null || par == null) return '<td class="p-1 border border-slate-200 dark:border-slate-700 font-mono text-center">-</td>';
                const diff = score - par;
                let badge = 'text-slate-800 dark:text-slate-200 font-medium';
                if (diff <= -2) {
                    badge = 'bg-amber-200 text-amber-900 dark:bg-amber-950 dark:text-amber-200 font-extrabold px-1 rounded';
                } else if (diff === -1) {
                    badge = 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 font-bold px-1 rounded';
                } else if (diff === 0) {
                    badge = 'text-slate-700 dark:text-slate-300';
                } else if (diff === 1) {
                    badge = 'text-slate-900 dark:text-slate-100 font-semibold';
                } else {
                    badge = 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 font-semibold px-1 rounded';
                }
                return `<td class="p-1 border border-slate-200 dark:border-slate-700 font-mono text-center"><span class="${badge}">${score}</span></td>`;
            }

            let fPars = '', fScores = '', fHeaders = '';
            for (let i = 0; i < 9; i++) {
                fHeaders += `<th class="p-1 border border-slate-200 dark:border-slate-700 text-center font-medium">${i+1}</th>`;
                fPars += `<td class="p-1 border border-slate-200 dark:border-slate-700 text-center text-slate-400 font-mono">${p.pars[i] || '-'}</td>`;
                fScores += formatHole(p.scores[i], p.pars[i]);
            }
            const fOutPar = p.pars[9] != null ? p.pars[9] : '-';
            const fOutScore = p.scores[9] != null ? p.scores[9] : '-';

            let bPars = '', bScores = '', bHeaders = '';
            for (let i = 10; i < 19; i++) {
                bHeaders += `<th class="p-1 border border-slate-200 dark:border-slate-700 text-center font-medium">${i}</th>`;
                bPars += `<td class="p-1 border border-slate-200 dark:border-slate-700 text-center text-slate-400 font-mono">${p.pars[i] || '-'}</td>`;
                bScores += formatHole(p.scores[i], p.pars[i]);
            }
            const bInPar = p.pars[19] != null ? p.pars[19] : '-';
            const bInScore = p.scores[19] != null ? p.scores[19] : '-';

            const totPar = p.pars[20] != null ? p.pars[20] : '-';
            const totScore = p.scores[20] != null ? p.scores[20] : '-';

            holeByHole = `
            <div class="mt-2 text-[10px] overflow-x-auto">
                <table class="w-full border-collapse border border-slate-200 dark:border-slate-700">
                    <thead class="bg-slate-100 dark:bg-slate-900/60 text-slate-600 dark:text-slate-400">
                        <tr>
                            <th class="p-1 border border-slate-200 dark:border-slate-700 text-left font-semibold">Loch</th>
                            ${fHeaders}
                            <th class="p-1 border border-slate-200 dark:border-slate-700 font-bold bg-slate-200/60 dark:bg-slate-800">OUT</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr class="text-slate-500">
                            <td class="p-1 border border-slate-200 dark:border-slate-700 font-semibold text-slate-400">Par</td>
                            ${fPars}
                            <td class="p-1 border border-slate-200 dark:border-slate-700 text-center font-mono font-semibold bg-slate-100/60 dark:bg-slate-800/60">${fOutPar}</td>
                        </tr>
                        <tr>
                            <td class="p-1 border border-slate-200 dark:border-slate-700 font-semibold text-slate-700 dark:text-slate-300">Score</td>
                            ${fScores}
                            <td class="p-1 border border-slate-200 dark:border-slate-700 text-center font-mono font-bold bg-slate-200/60 dark:bg-slate-800">${fOutScore}</td>
                        </tr>
                    </tbody>
                </table>

                <table class="w-full border-collapse border border-slate-200 dark:border-slate-700 mt-1">
                    <thead class="bg-slate-100 dark:bg-slate-900/60 text-slate-600 dark:text-slate-400">
                        <tr>
                            <th class="p-1 border border-slate-200 dark:border-slate-700 text-left font-semibold">Loch</th>
                            ${bHeaders}
                            <th class="p-1 border border-slate-200 dark:border-slate-700 font-bold bg-slate-200/60 dark:bg-slate-800">IN</th>
                            <th class="p-1 border border-slate-200 dark:border-slate-700 font-bold bg-blue-100 dark:bg-blue-900/40 text-blue-900 dark:text-blue-200">TOT</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr class="text-slate-500">
                            <td class="p-1 border border-slate-200 dark:border-slate-700 font-semibold text-slate-400">Par</td>
                            ${bPars}
                            <td class="p-1 border border-slate-200 dark:border-slate-700 text-center font-mono font-semibold bg-slate-100/60 dark:bg-slate-800/60">${bInPar}</td>
                            <td class="p-1 border border-slate-200 dark:border-slate-700 text-center font-mono font-bold bg-slate-100/60 dark:bg-slate-800/60">${totPar}</td>
                        </tr>
                        <tr>
                            <td class="p-1 border border-slate-200 dark:border-slate-700 font-semibold text-slate-700 dark:text-slate-300">Score</td>
                            ${bScores}
                            <td class="p-1 border border-slate-200 dark:border-slate-700 text-center font-mono font-bold bg-slate-200/60 dark:bg-slate-800">${bInScore}</td>
                            <td class="p-1 border border-slate-200 dark:border-slate-700 font-extrabold bg-blue-50 dark:bg-blue-950/60 text-blue-800 dark:text-sky-300 font-mono text-center">${totScore}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            `;
        }

        playerHtml += `
        <div class="${cardBg} p-3 rounded-xl border">
            <div class="flex justify-between items-start">
                <div>
                    <div class="font-bold text-xs sm:text-sm text-slate-900 dark:text-white flex items-center gap-1.5">
                        <span>${p.player_name}</span>
                        ${isStreich ? '<span class="text-[10px] px-1.5 py-0.2 bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400 rounded-sm font-semibold">Streichergebnis</span>' : ''}
                    </div>
                    <div class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                        HCP: <strong class="text-slate-700 dark:text-slate-300">${p.hcp || '-'}</strong>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-xs sm:text-sm font-extrabold text-blue-700 dark:text-sky-400">
                        ${p.cr_diff ? (p.cr_diff > 0 ? '+' + p.cr_diff : p.cr_diff) + ' ü. CR' : '-'}
                    </div>
                    <div class="text-[11px] text-slate-500 font-mono">
                        Brutto: ${p.brutto || '-'}
                    </div>
                </div>
            </div>
            ${holeByHole}
        </div>
        `;
    });

    if (players.length === 0) {
        playerHtml = '<p class="text-center py-6 text-xs text-slate-400">Keine Spieler-Einzelergebnisse hinterlegt.</p>';
    }
    document.getElementById('modalPlayersList').innerHTML = playerHtml;

    switchModalTab('teams');
    const modal = document.getElementById('detailModal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function closeModal() {
    const modal = document.getElementById('detailModal');
    if (modal) {
        modal.classList.remove('flex');
        modal.classList.add('hidden');
    }
}

function closeModalOnBackdrop(e) {
    if (e.target.id === 'detailModal') {
        closeModal();
    }
}

function switchModalTab(tabName) {
    currentModalTab = tabName;
    const isTeams = tabName === 'teams';
    document.getElementById('tabBtnTeams').className = isTeams
        ? 'py-2 px-2 text-xs font-semibold rounded-lg bg-blue-700 text-white shadow-xs transition-all text-center'
        : 'py-2 px-2 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-300 transition-all text-center hover:text-slate-900 dark:hover:text-white';
    document.getElementById('tabBtnPlayers').className = !isTeams
        ? 'py-2 px-2 text-xs font-semibold rounded-lg bg-blue-700 text-white shadow-xs transition-all text-center'
        : 'py-2 px-2 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-300 transition-all text-center hover:text-slate-900 dark:hover:text-white';
    document.getElementById('tabContentTeams').classList.toggle('hidden', !isTeams);
    document.getElementById('tabContentPlayers').classList.toggle('hidden', isTeams);
}

// 4. Initialisierung & Event Listener Bindings
function init() {
    // Header & Share Modal Bindings
    document.getElementById('openShareBtn')?.addEventListener('click', openShareModal);
    document.getElementById('closeShareModalBtn')?.addEventListener('click', closeShareModal);
    document.getElementById('shareModal')?.addEventListener('click', closeShareModalOnBackdrop);
    document.getElementById('copyShareBtn')?.addEventListener('click', copyShareUrl);
    document.getElementById('shareWhatsAppBtn')?.addEventListener('click', shareViaWhatsApp);
    document.getElementById('shareEmailBtn')?.addEventListener('click', shareViaEmail);
    document.getElementById('systemShareBtn')?.addEventListener('click', triggerSystemShare);

    // Detail Modal Bindings
    document.getElementById('closeDetailModalBtn')?.addEventListener('click', closeModal);
    document.getElementById('detailModal')?.addEventListener('click', closeModalOnBackdrop);
    document.getElementById('tabBtnTeams')?.addEventListener('click', () => switchModalTab('teams'));
    document.getElementById('tabBtnPlayers')?.addEventListener('click', () => switchModalTab('players'));

    // Global Table Toggle
    document.getElementById('toggleAllBtn')?.addEventListener('click', toggleAllTableMatchdays);

    // Year Selector Event Delegation
    document.getElementById('yearSelector')?.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-year]');
        if (btn && btn.dataset.year) {
            setYear(btn.dataset.year);
        }
    });

    // Team Selector Event Delegation
    document.getElementById('teamSelector')?.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-team]');
        if (btn && btn.dataset.team) {
            setTeam(btn.dataset.team);
        }
    });

    // Standings Table Event Delegation (Auf-/Zuklappen von Spieltagen pro Club)
    document.getElementById('standingsTableBody')?.addEventListener('click', (e) => {
        const row = e.target.closest('[data-club-idx]');
        if (row && row.dataset.clubIdx !== undefined) {
            toggleClubMatchdays(row.dataset.clubIdx);
        }
    });

    // Matchdays Grid Event Delegation (Öffnen der Spieltagsdetails)
    document.getElementById('matchdaysGrid')?.addEventListener('click', (e) => {
        const card = e.target.closest('[data-day-key]');
        if (card && card.dataset.dayKey) {
            openMatchdayModal(card.dataset.dayKey);
        }
    });

    // Initiale Ansicht setzen
    setYear(currentYear, false);
    setTeam(currentTeam, false);
    renderView();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// 5. PWA Service Worker Registrierung
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('./sw.js')
            .then((reg) => {
                console.log('[PWA] Service Worker erfolgreich registriert:', reg.scope);
            })
            .catch((err) => {
                console.warn('[PWA] Service Worker Registrierung fehlgeschlagen:', err);
            });
    });
}
