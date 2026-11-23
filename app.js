// =============================================================================
// GV NRW AK 50 Herren - Web-App Logik (app.js)
// Strikte CSP- & DOM-Sicherheit: textContent, createElement, sicheres DOM-Rendering
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

// 2. DOM-Hilfsfunktion für sicheres Erstellen von Elementen (XSS-frei)
function el(tag, classes = '', text = null) {
    const elem = document.createElement(tag);
    if (classes) elem.className = classes;
    if (text !== null && text !== undefined) elem.textContent = text;
    return elem;
}

// 3. Daten & Initialer Zustand
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

// 4. UI-Hilfsfunktionen & Sharing
function showToast(message, icon = '📋') {
    const toast = document.getElementById('toastNotification');
    const msgEl = document.getElementById('toastMessage');
    const iconEl = document.getElementById('toastIcon');
    if (!toast) return;
    if (msgEl) msgEl.textContent = message;
    if (iconEl) iconEl.textContent = icon;
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
    if (subTitle) subTitle.textContent = `⛳ GC Mülheim ${currentTeam} • Saison ${currentYear}`;
    if (input) input.value = url;

    const copyBtn = document.getElementById('copyShareBtn');
    if (copyBtn) copyBtn.textContent = 'Kopieren';

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
        if (btn) btn.textContent = 'Kopiert! ✓';
        showToast('Link erfolgreich kopiert!', '🔗');
        setTimeout(() => {
            if (btn) btn.textContent = 'Kopieren';
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
    const elId = document.getElementById(`clubMatchdays-${idx}`);
    const arrow = document.getElementById(`clubArrow-${idx}`);
    if (!elId) return;
    const isHidden = elId.classList.contains('hidden');
    elId.classList.toggle('hidden', !isHidden);
    if (arrow) arrow.textContent = isHidden ? '▴' : '▾';
}

function toggleAllTableMatchdays() {
    allTableExpanded = !allTableExpanded;
    document.querySelectorAll('[id^="clubMatchdays-"]').forEach(elem => {
        elem.classList.toggle('hidden', !allTableExpanded);
    });
    document.querySelectorAll('[id^="clubArrow-"]').forEach(arrow => {
        arrow.textContent = allTableExpanded ? '▴' : '▾';
    });
    const btn = document.getElementById('toggleAllBtn');
    if (btn) {
        btn.replaceChildren();
        btn.appendChild(el('span', '', allTableExpanded ? 'Verbergen ' : 'Spieltage '));
        btn.appendChild(el('span', '', allTableExpanded ? '▴' : '▾'));
    }
}

// 5. Sicheres DOM-Rendering für Tabellen, Grid & Modal (Priorität 2)
function renderView() {
    const yearData = GVNRW_DATA[currentYear] || {};
    const groupData = yearData[currentTeam];
    const tableBody = document.getElementById('standingsTableBody');
    const matchdaysGrid = document.getElementById('matchdaysGrid');
    const noticeContainer = document.getElementById('tableNoticeContainer');

    if (!groupData) {
        const titleEl = document.getElementById('leagueGroupTitle');
        if (titleEl) titleEl.textContent = 'Keine Daten';
        if (tableBody) {
            tableBody.replaceChildren();
            const tr = el('tr');
            const td = el('td', 'py-6 text-center text-slate-400', 'Keine Daten für dieses Jahr verfügbar.');
            td.colSpan = 4;
            tr.appendChild(td);
            tableBody.appendChild(tr);
        }
        if (matchdaysGrid) matchdaysGrid.replaceChildren();
        return;
    }

    const groupName = groupData.group_name || 'Gruppe';
    const groupTitleEl = document.getElementById('leagueGroupTitle');
    if (groupTitleEl) groupTitleEl.textContent = `${groupName} (${currentYear})`;

    const subDescEl = document.getElementById('subHeaderDesc');
    if (subDescEl) subDescEl.textContent = `AK 50 Herren ${currentYear} • GC Mülheim ${currentTeam}`;

    const teams = groupData.teams || [];
    const muelheimTeam = teams.find(t => (t.club || '').toLowerCase().includes('mülheim'));
    const rankBadge = document.getElementById('myRankBadge');
    const ptsTag = document.getElementById('seasonPointsTag');

    if (muelheimTeam) {
        if (rankBadge) rankBadge.textContent = `Rang #${muelheimTeam.rank}`;
        if (ptsTag) ptsTag.textContent = `${muelheimTeam.points} Punkte`;
    } else {
        if (rankBadge) rankBadge.textContent = '-';
        if (ptsTag) ptsTag.textContent = '';
    }

    // Sichere Tabellengenerierung
    if (tableBody) {
        tableBody.replaceChildren();
        teams.forEach((t, idx) => {
            const isMuelheim = (t.club || '').toLowerCase().includes('mülheim');
            const rowBg = isMuelheim
                ? 'bg-blue-50/90 dark:bg-blue-950/60 font-bold border-l-4 border-blue-600'
                : (idx % 2 === 0 ? 'bg-white dark:bg-slate-800' : 'bg-slate-50/75 dark:bg-slate-800/40');

            const tr = el('tr', `${rowBg} hover:bg-blue-50/50 dark:hover:bg-slate-700/50 transition-colors cursor-pointer`);
            tr.dataset.clubIdx = String(idx);

            // Rang
            const tdRank = el('td', 'py-2 px-2 text-center align-middle');
            let rankCls = 'inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200';
            if (t.rank === '1' || t.rank === 1) rankCls = 'inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300';
            else if (t.rank === '2' || t.rank === 2) rankCls = 'inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-slate-200 text-slate-800 border border-slate-300';
            else if (t.rank === '3' || t.rank === 3) rankCls = 'inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-orange-100 text-orange-900 border border-orange-300';
            tdRank.appendChild(el('span', rankCls, String(t.rank || '-')));
            tr.appendChild(tdRank);

            // Club Name & Toggle
            const tdClub = el('td', 'py-2 px-2.5');
            const clubHeader = el('div', 'font-medium text-slate-900 dark:text-slate-100 flex items-center justify-between');
            const clubTitle = el('span', 'flex items-center gap-1', t.club || '-');
            if (isMuelheim) {
                clubTitle.appendChild(el('span', 'text-xs', ' 🏌️‍♂️'));
            }
            clubHeader.appendChild(clubTitle);

            if (t.matchdays && Object.keys(t.matchdays).length > 0) {
                const toggleBtn = el('button', 'inline-flex items-center gap-0.5 text-[10px] text-slate-400 hover:text-blue-700 dark:hover:text-sky-400 px-1 py-0.2 rounded hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors ml-1.5');
                toggleBtn.type = 'button';
                toggleBtn.dataset.action = 'toggle-club';
                toggleBtn.dataset.clubIdx = String(idx);
                toggleBtn.appendChild(el('span', '', 'Spieltage'));
                const arrow = el('span', '', '▾');
                arrow.id = `clubArrow-${idx}`;
                toggleBtn.appendChild(arrow);
                clubHeader.appendChild(toggleBtn);
            }
            tdClub.appendChild(clubHeader);

            // Ausklappbare Spieltagsübersicht
            if (t.matchdays && Object.keys(t.matchdays).length > 0) {
                const mdContainer = el('div', 'hidden mt-1 flex flex-wrap gap-1');
                mdContainer.id = `clubMatchdays-${idx}`;
                Object.entries(t.matchdays).forEach(([k, v]) => {
                    if (!v) return;
                    const isNachholer = String(v).includes('[Nachholer]');
                    const cleanVal = String(v).replace(' [Nachholer]', '');
                    const badgeCls = isNachholer
                        ? 'inline-block px-1.5 py-0.2 rounded text-[10px] bg-blue-600 text-white font-bold shadow-xs'
                        : 'inline-block px-1.5 py-0.2 rounded text-[10px] bg-slate-100 text-slate-700 dark:bg-slate-700/60 dark:text-slate-300 border border-slate-200 dark:border-slate-700';
                    const badge = el('span', badgeCls, `${isNachholer ? k + ' (Nachholer)' : k}: `);
                    badge.appendChild(el('strong', '', cleanVal));
                    mdContainer.appendChild(badge);
                });
                tdClub.appendChild(mdContainer);
            }
            tr.appendChild(tdClub);

            // Punkte
            const tdPoints = el('td', 'py-2 px-2.5 text-right font-bold text-blue-700 dark:text-sky-400 align-middle text-xs sm:text-sm', String(t.points != null ? t.points : '-'));
            tr.appendChild(tdPoints);

            // Ø über CR
            const tdAvgCr = el('td', 'py-2 px-2.5 text-right text-slate-500 dark:text-slate-400 font-mono align-middle text-xs', String(t.avg_cr != null ? t.avg_cr : '-'));
            tr.appendChild(tdAvgCr);

            tableBody.appendChild(tr);
        });
    }

    // Spielplan-Hinweise
    const matchdaysDetails = groupData.matchdays_details || {};
    const canceledList = Object.keys(matchdaysDetails).filter(k => matchdaysDetails[k].is_canceled);
    const rescheduledList = Object.keys(matchdaysDetails).filter(k => matchdaysDetails[k].is_rescheduled);

    if (noticeContainer) {
        noticeContainer.replaceChildren();
        if (canceledList.length > 0 || rescheduledList.length > 0) {
            let noteText = '';
            if (canceledList.length > 0 && rescheduledList.length > 0) {
                noteText = `Spielplan-Besonderheit (${groupName}): Der ${canceledList.join(', ')} fiel aus und wurde im Nachholtermin (${rescheduledList.join(', ')}) ausgetragen. Die Punkte fließen vollständig in das offizielle Endergebnis ein.`;
            } else if (canceledList.length > 0) {
                noteText = `Spielplan-Besonderheit (${groupName}): Folgende Spieltage fielen aus: ${canceledList.join(', ')}.`;
            } else {
                noteText = `Spielplan-Besonderheit (${groupName}): Enthält nachgeholte Spieltage: ${rescheduledList.join(', ')}. Alle Punkte fließen vollständig in das Endergebnis ein.`;
            }
            const box = el('div', 'px-4 py-2.5 bg-amber-50 dark:bg-amber-950/40 border-t border-amber-200/70 dark:border-amber-800/50 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2');
            box.appendChild(el('span', 'text-base leading-none', 'ℹ️'));
            box.appendChild(el('div', '', noteText));
            noticeContainer.appendChild(box);
        }
    }

    // Sichere Spieltags-Kacheln
    if (matchdaysGrid) {
        matchdaysGrid.replaceChildren();
        const dayKeys = Object.keys(matchdaysDetails).sort((a, b) => {
            const dateA = matchdaysDetails[a].date || '';
            const dateB = matchdaysDetails[b].date || '';
            if (dateA && dateB) return dateA.localeCompare(dateB);
            const idxA = (groupData.headers || []).indexOf(a);
            const idxB = (groupData.headers || []).indexOf(b);
            if (idxA >= 0 && idxB >= 0) return idxA - idxB;
            return (parseInt(a) || 0) - (parseInt(b) || 0);
        });

        if (dayKeys.length === 0) {
            matchdaysGrid.appendChild(el('p', 'col-span-2 text-center py-6 text-xs text-slate-400', 'Keine Spieltage für diese Gruppe hinterlegt.'));
            return;
        }

        dayKeys.forEach(dayKey => {
            const d = matchdaysDetails[dayKey];
            const myResult = (d.team_results || []).find(r => (r.team_name || '').toLowerCase().includes('mülheim'));
            let scoreText = '-';
            if (myResult) {
                if (myResult.score) {
                    scoreText = `${myResult.score} (${myResult.points || '0'} Pkt)`;
                } else if (myResult.points) {
                    scoreText = `${myResult.points} Pkt`;
                }
            }

            let cardClass = 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 shadow-xs hover:border-blue-500';
            if (d.is_canceled && d.linked_rescheduled_day) {
                cardClass = 'bg-blue-50/40 dark:bg-blue-950/20 border-2 border-blue-500 shadow-xs hover:border-blue-600';
            } else if (d.is_canceled) {
                cardClass = 'bg-amber-50/40 dark:bg-amber-950/20 border-dashed border-amber-300 dark:border-amber-700/60 opacity-85 hover:border-amber-400';
            } else if (d.is_rescheduled) {
                cardClass = 'bg-white dark:bg-slate-800 border-2 border-blue-400 dark:border-blue-600 shadow-xs hover:border-blue-500';
            }

            const card = el('div', `${cardClass} rounded-xl p-3.5 border transition-all cursor-pointer flex flex-col justify-between active:scale-[0.98]`);
            card.dataset.dayKey = dayKey;

            const topDiv = el('div');
            const headerRow = el('div', 'flex justify-between items-start mb-1 flex-wrap gap-1');

            const titleWrap = el('div');
            if (d.is_canceled && d.linked_rescheduled_day) {
                const wrap = el('div', 'flex items-center gap-2 flex-wrap');
                wrap.appendChild(el('span', 'font-extrabold text-sm text-slate-900 dark:text-white', d.day_name));
                wrap.appendChild(el('span', 'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-600 text-white shadow-xs', '🔄 Nachholer am 19.09.'));
                titleWrap.appendChild(wrap);
            } else if (d.is_rescheduled) {
                const wrap = el('div', 'flex items-center gap-2 flex-wrap');
                const canceledLabel = d.linked_canceled_day ? ` (Nachholer für ${d.linked_canceled_day})` : '';
                wrap.appendChild(el('span', 'font-extrabold text-sm text-slate-900 dark:text-white', `${d.day_name}${canceledLabel}`));
                wrap.appendChild(el('span', 'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-600 text-white shadow-xs', '🔄 Nachholspieltag'));
                titleWrap.appendChild(wrap);
            } else {
                titleWrap.appendChild(el('span', 'font-bold text-sm text-slate-900 dark:text-white', d.day_name));
            }
            headerRow.appendChild(titleWrap);

            const dateWrap = el('div');
            if (d.is_canceled && d.linked_rescheduled_day) {
                const rDiv = el('div', 'text-right');
                rDiv.appendChild(el('span', 'px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300 border border-amber-300', 'Urspr. 02.05. ausgefallen'));
                rDiv.appendChild(el('div', 'text-xs text-blue-600 dark:text-blue-400 font-bold font-mono mt-0.5', 'gespielt 19.09.'));
                dateWrap.appendChild(rDiv);
            } else if (d.is_canceled) {
                dateWrap.appendChild(el('span', 'px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300 border border-amber-300', 'Ausgefallen'));
                if (d.date) {
                    dateWrap.appendChild(el('span', 'text-[11px] text-slate-400 line-through font-mono ml-1', ` ${d.date}`));
                }
            } else if (d.is_rescheduled) {
                dateWrap.appendChild(el('span', 'text-[11px] text-blue-700 dark:text-blue-300 bg-blue-100 dark:bg-blue-950/80 px-2 py-0.5 rounded-md font-mono font-bold border border-blue-300 dark:border-blue-700', d.date || ''));
            } else {
                dateWrap.appendChild(el('span', 'text-[11px] text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-700/60 px-2 py-0.5 rounded-md font-mono', d.date || 'Termin folgt'));
            }
            headerRow.appendChild(dateWrap);
            topDiv.appendChild(headerRow);

            const venueText = d.venue ? d.venue : (d.is_canceled ? 'Spieltag fand nicht statt' : 'Spielort offen');
            topDiv.appendChild(el('p', 'text-xs text-slate-500 dark:text-slate-400 truncate mb-3', venueText));
            card.appendChild(topDiv);

            const bottomRow = el('div', 'flex justify-between items-center pt-2.5 border-t border-slate-100 dark:border-slate-700');
            bottomRow.appendChild(el('span', 'text-xs font-bold text-blue-700 dark:text-sky-400', scoreText));
            bottomRow.appendChild(el('span', 'text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1 font-medium', 'Details ➜'));
            card.appendChild(bottomRow);

            matchdaysGrid.appendChild(card);
        });
    }
}

// 6. Sicheres Modal-Rendering (Mannschaften & Spieler)
function openMatchdayModal(dayKey) {
    const groupData = GVNRW_DATA[currentYear]?.[currentTeam];
    const d = groupData?.matchdays_details?.[dayKey];
    if (!d) return;

    const titleEl = document.getElementById('modalDayTitle');
    const dateEl = document.getElementById('modalDayDate');
    const venueEl = document.getElementById('modalVenueText');
    const teeRow = document.getElementById('modalTeeRow');
    const teeText = document.getElementById('modalTeeText');

    if (titleEl) titleEl.textContent = d.day_name;
    if (dateEl) dateEl.textContent = d.date ? `Datum: ${d.date}` : 'Termin noch offen';
    if (venueEl) venueEl.textContent = d.venue || (d.is_canceled ? 'Spieltag ausgefallen' : 'Nicht spezifiziert');

    if (teeRow && teeText) {
        if (d.tee_info) {
            teeRow.style.display = 'block';
            teeText.textContent = d.tee_info;
        } else {
            teeRow.style.display = 'none';
        }
    }

    const bannerBox = document.getElementById('modalBannerContainer');
    if (bannerBox) {
        bannerBox.replaceChildren();
        if (d.is_canceled && d.linked_rescheduled_day) {
            const b = el('div', 'mb-3 p-3 rounded-xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-xs text-blue-900 dark:text-blue-200');
            b.appendChild(el('div', 'font-extrabold flex items-center gap-1 mb-1', '🔄 Spieltag wurde nachgeholt!'));
            b.appendChild(el('p', '', 'Dieser Spieltag war ursprünglich für den 02.05.2026 angesetzt, musste jedoch wetterbedingt abgesagt werden. Er wurde am 19.09.2026 im GC Essen-Heidhausen nachgeholt. Die hier angezeigten Ergebnisse und Punkte stammen von diesem Nachholtermin.'));
            bannerBox.appendChild(b);
        } else if (d.is_canceled) {
            const b = el('div', 'mb-3 p-3 rounded-xl bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800 text-xs text-amber-900 dark:text-amber-200');
            b.appendChild(el('div', 'font-bold flex items-center gap-1 mb-1', '⚠️ Spieltag ausgefallen / entfallen'));
            b.appendChild(el('p', '', 'Dieser Spieltag wurde nicht ausgetragen.'));
            bannerBox.appendChild(b);
        }
    }

    // Tab 1: Teams
    const teamBody = document.getElementById('modalTeamResultsBody');
    if (teamBody) {
        teamBody.replaceChildren();
        const results = d.team_results || [];
        if (results.length === 0) {
            const tr = el('tr');
            const td = el('td', 'py-6 text-center text-slate-400', 'Keine Mannschaftsergebnisse für diesen Spieltag.');
            td.colSpan = 4;
            tr.appendChild(td);
            teamBody.appendChild(tr);
        } else {
            results.forEach(r => {
                const isMuelheim = (r.team_name || '').toLowerCase().includes('mülheim');
                const rowBg = isMuelheim ? 'bg-blue-50/90 dark:bg-blue-950/60 font-bold' : '';
                const tr = el('tr', rowBg);

                tr.appendChild(el('td', 'py-2 px-2.5 text-center font-semibold text-slate-500', r.rank ? `#${r.rank}` : '-'));
                const tdName = el('td', 'py-2 px-2.5 font-medium text-slate-900 dark:text-white flex items-center gap-1.5', r.team_name || '-');
                if (isMuelheim) {
                    tdName.appendChild(el('span', 'text-xs', ' 🏌️‍♂️'));
                }
                tr.appendChild(tdName);

                tr.appendChild(el('td', 'py-2 px-2.5 text-right font-mono text-slate-700 dark:text-slate-300', String(r.score != null ? r.score : '-')));
                tr.appendChild(el('td', 'py-2 px-2.5 text-right font-bold text-blue-700 dark:text-sky-400', r.points ? `${r.points} Pkt` : '-'));
                teamBody.appendChild(tr);
            });
        }
    }

    // Tab 2: Players
    const playersList = document.getElementById('modalPlayersList');
    if (playersList) {
        playersList.replaceChildren();
        const players = d.players || [];
        if (players.length === 0) {
            playersList.appendChild(el('p', 'text-center py-6 text-xs text-slate-400', 'Keine Spieler-Einzelergebnisse hinterlegt.'));
        } else {
            players.forEach(p => {
                const isStreich = !!(p.is_streichergebnis || p.is_cutoff);
                const cardBg = isStreich
                    ? 'bg-slate-50/70 dark:bg-slate-800/40 border-dashed border-slate-300 dark:border-slate-700 opacity-75'
                    : 'bg-white dark:bg-slate-800/90 border-slate-200 dark:border-slate-700 shadow-2xs';

                const card = el('div', `${cardBg} p-3 rounded-xl border`);
                const headerRow = el('div', 'flex justify-between items-start');

                const leftDiv = el('div');
                const nameRow = el('div', 'font-bold text-xs sm:text-sm text-slate-900 dark:text-white flex items-center gap-1.5');
                const firstName = p.name || '';
                const lastName = p.familyname || '';
                const fullName = p.player_name || `${firstName} ${lastName}`.trim() || 'Spieler';
                nameRow.appendChild(el('span', '', fullName));
                if (isStreich) {
                    nameRow.appendChild(el('span', 'text-[10px] px-1.5 py-0.2 bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400 rounded-sm font-semibold', 'Streichergebnis'));
                }
                leftDiv.appendChild(nameRow);

                const hcpRow = el('div', 'text-[11px] text-slate-500 dark:text-slate-400 mt-0.5', 'HCP: ');
                hcpRow.appendChild(el('strong', 'text-slate-700 dark:text-slate-300', String(p.hcp || '-')));
                if (p.playinhcp) {
                    const spHcp = el('span', '', ' • Sp.HCP: ');
                    spHcp.appendChild(el('strong', 'text-slate-700 dark:text-slate-300', String(p.playinhcp)));
                    hcpRow.appendChild(spHcp);
                }
                leftDiv.appendChild(hcpRow);
                headerRow.appendChild(leftDiv);

                const rightDiv = el('div', 'text-right');
                const rawPlusCr = (p.plus_cr !== undefined && p.plus_cr !== null && p.plus_cr !== '') ? p.plus_cr : p.cr_diff;
                let plusCrText = '-';
                if (rawPlusCr !== undefined && rawPlusCr !== null && rawPlusCr !== '') {
                    const num = parseFloat(rawPlusCr);
                    plusCrText = (!isNaN(num) && num > 0 ? '+' + rawPlusCr : String(rawPlusCr)) + ' ü. CR';
                }
                rightDiv.appendChild(el('div', 'text-xs sm:text-sm font-extrabold text-blue-700 dark:text-sky-400 font-mono', plusCrText));

                const bruttoScore = p.erg_brutto || p.brutto || '-';
                rightDiv.appendChild(el('div', 'text-[11px] text-slate-500 font-mono', `Brutto: ${bruttoScore}`));
                headerRow.appendChild(rightDiv);

                card.appendChild(headerRow);

                // Loch-für-Loch Scorekarte
                if (p.pars && p.pars.length >= 21 && p.scores && p.scores.length >= 21) {
                    const tableWrap = el('div', 'mt-2 text-[10px] overflow-x-auto');

                    function formatHole(score, par) {
                        const td = el('td', 'p-1 border border-slate-200 dark:border-slate-700 font-mono text-center');
                        if (score == null || par == null) {
                            td.textContent = '-';
                            return td;
                        }
                        const diff = score - par;
                        let badgeCls = 'text-slate-800 dark:text-slate-200 font-medium';
                        if (diff <= -2) badgeCls = 'bg-amber-200 text-amber-900 dark:bg-amber-950 dark:text-amber-200 font-extrabold px-1 rounded';
                        else if (diff === -1) badgeCls = 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 font-bold px-1 rounded';
                        else if (diff === 0) badgeCls = 'text-slate-700 dark:text-slate-300';
                        else if (diff === 1) badgeCls = 'text-slate-900 dark:text-slate-100 font-semibold';
                        else badgeCls = 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 font-semibold px-1 rounded';
                        td.appendChild(el('span', badgeCls, String(score)));
                        return td;
                    }

                    // Front 9 Tabelle
                    const tableF = el('table', 'w-full border-collapse border border-slate-200 dark:border-slate-700');
                    const theadF = el('thead', 'bg-slate-100 dark:bg-slate-900/60 text-slate-600 dark:text-slate-400');
                    const trHeaderF = el('tr');
                    trHeaderF.appendChild(el('th', 'p-1 border border-slate-200 dark:border-slate-700 text-left font-semibold', 'Loch'));
                    for (let i = 0; i < 9; i++) {
                        trHeaderF.appendChild(el('th', 'p-1 border border-slate-200 dark:border-slate-700 text-center font-medium', String(i + 1)));
                    }
                    trHeaderF.appendChild(el('th', 'p-1 border border-slate-200 dark:border-slate-700 font-bold bg-slate-200/60 dark:bg-slate-800', 'OUT'));
                    theadF.appendChild(trHeaderF);
                    tableF.appendChild(theadF);

                    const tbodyF = el('tbody');
                    const trParF = el('tr', 'text-slate-500');
                    trParF.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 font-semibold text-slate-400', 'Par'));
                    for (let i = 0; i < 9; i++) {
                        trParF.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 text-center text-slate-400 font-mono', String(p.pars[i] != null ? p.pars[i] : '-')));
                    }
                    trParF.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 text-center font-mono font-semibold bg-slate-100/60 dark:bg-slate-800/60', String(p.pars[9] != null ? p.pars[9] : '-')));
                    tbodyF.appendChild(trParF);

                    const trScoreF = el('tr');
                    trScoreF.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 font-semibold text-slate-700 dark:text-slate-300', 'Score'));
                    for (let i = 0; i < 9; i++) {
                        trScoreF.appendChild(formatHole(p.scores[i], p.pars[i]));
                    }
                    trScoreF.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 text-center font-mono font-bold bg-slate-200/60 dark:bg-slate-800', String(p.scores[9] != null ? p.scores[9] : '-')));
                    tbodyF.appendChild(trScoreF);
                    tableF.appendChild(tbodyF);
                    tableWrap.appendChild(tableF);

                    // Back 9 Tabelle
                    const tableB = el('table', 'w-full border-collapse border border-slate-200 dark:border-slate-700 mt-1');
                    const theadB = el('thead', 'bg-slate-100 dark:bg-slate-900/60 text-slate-600 dark:text-slate-400');
                    const trHeaderB = el('tr');
                    trHeaderB.appendChild(el('th', 'p-1 border border-slate-200 dark:border-slate-700 text-left font-semibold', 'Loch'));
                    for (let i = 10; i < 19; i++) {
                        trHeaderB.appendChild(el('th', 'p-1 border border-slate-200 dark:border-slate-700 text-center font-medium', String(i)));
                    }
                    trHeaderB.appendChild(el('th', 'p-1 border border-slate-200 dark:border-slate-700 font-bold bg-slate-200/60 dark:bg-slate-800', 'IN'));
                    trHeaderB.appendChild(el('th', 'p-1 border border-slate-200 dark:border-slate-700 font-bold bg-blue-100 dark:bg-blue-900/40 text-blue-900 dark:text-blue-200', 'TOT'));
                    theadB.appendChild(trHeaderB);
                    tableB.appendChild(theadB);

                    const tbodyB = el('tbody');
                    const trParB = el('tr', 'text-slate-500');
                    trParB.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 font-semibold text-slate-400', 'Par'));
                    for (let i = 10; i < 19; i++) {
                        trParB.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 text-center text-slate-400 font-mono', String(p.pars[i] != null ? p.pars[i] : '-')));
                    }
                    trParB.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 text-center font-mono font-semibold bg-slate-100/60 dark:bg-slate-800/60', String(p.pars[19] != null ? p.pars[19] : '-')));
                    trParB.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 text-center font-mono font-bold bg-slate-100/60 dark:bg-slate-800/60', String(p.pars[20] != null ? p.pars[20] : '-')));
                    tbodyB.appendChild(trParB);

                    const trScoreB = el('tr');
                    trScoreB.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 font-semibold text-slate-700 dark:text-slate-300', 'Score'));
                    for (let i = 10; i < 19; i++) {
                        trScoreB.appendChild(formatHole(p.scores[i], p.pars[i]));
                    }
                    trScoreB.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 text-center font-mono font-bold bg-slate-200/60 dark:bg-slate-800', String(p.scores[19] != null ? p.scores[19] : '-')));
                    trScoreB.appendChild(el('td', 'p-1 border border-slate-200 dark:border-slate-700 font-extrabold bg-blue-50 dark:bg-blue-950/60 text-blue-800 dark:text-sky-300 font-mono text-center', String(p.scores[20] != null ? p.scores[20] : '-')));
                    tbodyB.appendChild(trScoreB);
                    tableB.appendChild(tbodyB);
                    tableWrap.appendChild(tableB);

                    card.appendChild(tableWrap);
                }

                playersList.appendChild(card);
            });
        }
    }

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
    const tabTeams = document.getElementById('tabBtnTeams');
    const tabPlayers = document.getElementById('tabBtnPlayers');
    const contentTeams = document.getElementById('tabContentTeams');
    const contentPlayers = document.getElementById('tabContentPlayers');

    if (tabTeams) {
        tabTeams.className = isTeams
            ? 'py-2 px-2 text-xs font-semibold rounded-lg bg-blue-700 text-white shadow-xs transition-all text-center'
            : 'py-2 px-2 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-300 transition-all text-center hover:text-slate-900 dark:hover:text-white';
    }
    if (tabPlayers) {
        tabPlayers.className = !isTeams
            ? 'py-2 px-2 text-xs font-semibold rounded-lg bg-blue-700 text-white shadow-xs transition-all text-center'
            : 'py-2 px-2 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-300 transition-all text-center hover:text-slate-900 dark:hover:text-white';
    }
    if (contentTeams) contentTeams.classList.toggle('hidden', !isTeams);
    if (contentPlayers) contentPlayers.classList.toggle('hidden', isTeams);
}

// 7. Initialisierung & Event Listener Bindings
function init() {
    document.getElementById('openShareBtn')?.addEventListener('click', openShareModal);
    document.getElementById('closeShareModalBtn')?.addEventListener('click', closeShareModal);
    document.getElementById('shareModal')?.addEventListener('click', closeShareModalOnBackdrop);
    document.getElementById('copyShareBtn')?.addEventListener('click', copyShareUrl);
    document.getElementById('shareWhatsAppBtn')?.addEventListener('click', shareViaWhatsApp);
    document.getElementById('shareEmailBtn')?.addEventListener('click', shareViaEmail);
    document.getElementById('systemShareBtn')?.addEventListener('click', triggerSystemShare);

    document.getElementById('closeDetailModalBtn')?.addEventListener('click', closeModal);
    document.getElementById('detailModal')?.addEventListener('click', closeModalOnBackdrop);
    document.getElementById('tabBtnTeams')?.addEventListener('click', () => switchModalTab('teams'));
    document.getElementById('tabBtnPlayers')?.addEventListener('click', () => switchModalTab('players'));

    document.getElementById('toggleAllBtn')?.addEventListener('click', toggleAllTableMatchdays);

    document.getElementById('yearSelector')?.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-year]');
        if (btn && btn.dataset.year) {
            setYear(btn.dataset.year);
        }
    });

    document.getElementById('teamSelector')?.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-team]');
        if (btn && btn.dataset.team) {
            setTeam(btn.dataset.team);
        }
    });

    document.getElementById('standingsTableBody')?.addEventListener('click', (e) => {
        const row = e.target.closest('[data-club-idx]');
        if (row && row.dataset.clubIdx !== undefined) {
            toggleClubMatchdays(row.dataset.clubIdx);
        }
    });

    document.getElementById('matchdaysGrid')?.addEventListener('click', (e) => {
        const card = e.target.closest('[data-day-key]');
        if (card && card.dataset.dayKey) {
            openMatchdayModal(card.dataset.dayKey);
        }
    });

    setYear(currentYear, false);
    setTeam(currentTeam, false);
    renderView();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// 8. PWA Service Worker Registrierung
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
