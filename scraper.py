"""
Golfverband NRW (GV NRW) - AK 50 Herren Scraper & Interactive Mobile Viewer
---------------------------------------------------------------------------
Scraper und mobil-optimierte Web-App für die AK 50 Herren des GV NRW.

Funktionen:
- Download & HTML-Tabellen-Parsing mit BeautifulSoup
- Offizielle GV NRW Liga-Portal-Anbindung (gvnrw.liga.golf)
- Wechsel zwischen Saisons (2024, 2025, 2026, 2027)
- Wechsel zwischen GC Mülheim 1 und GC Mülheim 2
- Klickbare Spieltage mit:
    * Gesamtergebnisse & Punkteverteilung aller Mannschaften
    * Einzelspieler-Ergebnisse (Brutto, über CR, HCP, Streichergebnis, Loch-für-Loch)
    * Spielort, Platzdaten, Par und Course Rating
- Modernes Tailwind CSS Design mit sauberem Tabellenlayout (alternierende Zeilen)
- Zeitstempel 'Letztes Update: [Datum, Uhrzeit]'
- Speichert 'ergebnisse.html'
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime
import hashlib
import html
import json
import logging
import math
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
import struct
import sys
from typing import Any
import zlib

from bs4 import BeautifulSoup
import requests


def load_env() -> None:
    """
    Lädt Umgebungsvariablen aus einer lokalen secrets.env-Datei im selben Verzeichnis
    wie dieses Skript, ohne externe Bibliotheken (Termux-kompatibel).
    """
    base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.abspath(".")
    env_path = os.path.join(base_dir, "secrets.env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(
                        key.strip(), val.strip().strip('"').strip("'")
                    )
    except Exception as e:
        logging.getLogger(__name__).warning(f"Konnte .env nicht laden: {e}")


# Umgebungsvariablen beim Start laden
load_env()

# GitHub Pages Deployment Konfiguration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER = os.environ.get("GITHUB_USER", "dirkono")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "ak50-muelheim")

# Konfiguration
GVNRW_LIGA_PORTAL = "https://gvnrw.liga.golf"
GVNRW_BACKEND_URL = "https://gvnrw-backend.liga.golf"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15

# Vordefiniertes Mapping für schnelle Abfragen von GC Mülheim 1 und 2
KNOWN_MUELHEIM_GROUPS = {
    "2024": {
        "1": {"league_id": "3325", "group_name": "Liga 3.C", "team_id": 14699},
        "2": {"league_id": "3359", "group_name": "Liga 6.I", "team_id": 14915},
    },
    "2025": {
        "1": {"league_id": "3582", "group_name": "Liga 2.A", "team_id": 16505},
        "2": {"league_id": "3619", "group_name": "Liga 6.H", "team_id": 16699},
    },
    "2026": {
        "1": {"league_id": "3845", "group_name": "Liga 2.A", "team_id": 17503},
        "2": {"league_id": "3882", "group_name": "Liga 6.H", "team_id": 17713},
    },
    "2027": {
        "1": {"league_id": "4110", "group_name": "Liga 2.A", "team_id": 18622},
        "2": {"league_id": "4150", "group_name": "Liga 6.K", "team_id": 18832},
    },
}

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Sicherheits- & Validierungsfunktionen (Prioritäten 2, 3 & 4)
# =============================================================================

MAX_STRING_LENGTH = 80
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5 MB Download-Limit
REQUEST_TIMEOUT = 15


def sanitize_text(val: Any, max_length: int = MAX_STRING_LENGTH) -> str:
    """
    Strikte Validierung und Bereinigung von Texten (Priorität 3):
    - Entfernt/verwirft gefährliche Zeichen (<, >, {, })
    - Begrenzt auf max_length Zeichen (Standard: 80 Zeichen)
    - Wendet html.escape(..., quote=True) an (Priorität 2)
    """
    if val is None:
        return ""
    s = str(val).strip()
    for char in ("<", ">", "{", "}"):
        s = s.replace(char, "")
    s = s[:max_length]
    return html.escape(s, quote=True)


def sanitize_numeric(val: Any, is_float: bool = False, default: Any = "") -> int | float | str:
    """
    Strikte Validierung von Zahlenwerten (Priorität 3):
    Wandelt Werte strikt in int oder float um. Ungültige Eingaben werden abgefangen.
    """
    if val is None or val == "":
        return default
    try:
        clean_str = str(val).strip().replace(",", ".")
        if is_float:
            return float(clean_str)
        return int(float(clean_str))
    except (ValueError, TypeError):
        return default


def sanitize_url(url: Any) -> str:
    """
    Allowlisting für URLs (Priorität 3):
    Erlaubt ausschließlich Links, die strikt mit https:// beginnen.
    """
    if not url:
        return ""
    s = str(url).strip()
    if s.startswith("https://"):
        return s
    return ""


def safe_request_get(
    url: str,
    headers: dict | None = None,
    timeout: int = REQUEST_TIMEOUT,
    max_size: int = MAX_RESPONSE_SIZE,
) -> requests.Response:
    """
    Download-Limit & Timeout für GET (Priorität 4):
    Begrenzt auf timeout=15s und bricht ab, falls die Antwort > 5 MB ist.
    """
    resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
    resp.raise_for_status()

    cl = resp.headers.get("Content-Length")
    if cl:
        try:
            if int(cl) > max_size:
                raise ValueError(f"Download-Limit überschritten: Content-Length {cl} > {max_size} Bytes")
        except ValueError as e:
            if "Download-Limit" in str(e):
                raise

    content = bytearray()
    for chunk in resp.iter_content(chunk_size=65536):
        content.extend(chunk)
        if len(content) > max_size:
            raise ValueError(f"Download-Limit überschritten: Antwortgröße > {max_size} Bytes")

    resp._content = bytes(content)
    return resp


def safe_request_post(
    url: str,
    json_data: dict | None = None,
    headers: dict | None = None,
    timeout: int = REQUEST_TIMEOUT,
    max_size: int = MAX_RESPONSE_SIZE,
) -> requests.Response:
    """
    Download-Limit & Timeout für POST (Priorität 4):
    Begrenzt auf timeout=15s und bricht ab, falls die Antwort > 5 MB ist.
    """
    resp = requests.post(url, headers=headers, json=json_data, timeout=timeout, stream=True)
    resp.raise_for_status()

    cl = resp.headers.get("Content-Length")
    if cl:
        try:
            if int(cl) > max_size:
                raise ValueError(f"Download-Limit überschritten: Content-Length {cl} > {max_size} Bytes")
        except ValueError as e:
            if "Download-Limit" in str(e):
                raise

    content = bytearray()
    for chunk in resp.iter_content(chunk_size=65536):
        content.extend(chunk)
        if len(content) > max_size:
            raise ValueError(f"Download-Limit überschritten: Antwortgröße > {max_size} Bytes")

    resp._content = bytes(content)
    return resp


def validate_dataset_plausibility(dataset: dict[str, Any]) -> tuple[bool, str]:
    """
    Not-Aus Plausibilitätsprüfung (Priorität 4):
    Prüft, ob mindestens 'Mülheim' im Team-Datensatz und >= 1 Spieltag vorhanden sind.
    """
    if not dataset or not isinstance(dataset, dict):
        return False, "Not-Aus: Datensatz ist leer oder ungültig."

    muelheim_found = False
    total_matchdays = 0

    for year, teams_by_key in dataset.items():
        if not isinstance(teams_by_key, dict):
            continue
        for team_key, table_data in teams_by_key.items():
            if not isinstance(table_data, dict):
                continue
            for t in table_data.get("teams", []):
                club = t.get("club", "")
                if "mülheim" in club.lower():
                    muelheim_found = True

            md_details = table_data.get("matchdays_details", {})
            if isinstance(md_details, dict):
                total_matchdays += len(md_details)

    if not muelheim_found:
        return False, "Not-Aus: Kein Team mit 'Mülheim' im Datensatz gefunden (mögliche fehlerhafte oder manipulierte Seite)."

    if total_matchdays < 1:
        return False, "Not-Aus: Keine Spieltage im Datensatz gefunden (mindestens 1 Spieltag erforderlich)."

    return True, ""


# =============================================================================
# Datenmodelle
# =============================================================================

@dataclass
class PlayerScore:
    """Repräsentiert die Leistung eines einzelnen Spielers an einem Spieltag."""
    name: str
    familyname: str
    hcp: str = ""
    playinhcp: str = ""
    erg_brutto: str = ""
    plus_cr: str = ""
    is_streichergebnis: bool = False
    pars: list[int] = field(default_factory=list)
    scores: list[int] = field(default_factory=list)


@dataclass
class MatchdayTeamResult:
    """Ergebnis einer Mannschaft an einem Spieltag (Schlagzahl & Punkte)."""
    team_name: str
    score: str
    points: str
    is_home: bool = False
    rank: int = 0


@dataclass
class MatchdayDetail:
    """Detaillierte Informationen zu einem Spieltag."""
    day_name: str
    date: str = ""
    venue: str = ""
    tee_info: str = ""
    team_results: list[MatchdayTeamResult] = field(default_factory=list)
    players: list[PlayerScore] = field(default_factory=list)
    is_canceled: bool = False
    is_rescheduled: bool = False
    status_note: str = ""
    linked_rescheduled_day: str = ""
    linked_canceled_day: str = ""


@dataclass
class TeamStanding:
    """Platzierung einer Mannschaft in der Ligatabelle."""
    rank: str
    club: str
    points: str
    team_id: str = ""
    matchdays: dict[str, str] = field(default_factory=dict)
    cr_score: str = ""
    avg_cr: str = ""
    raw_data: list[str] = field(default_factory=list)


@dataclass
class LeagueGroupTable:
    """Komplette Ligatabelle inklusive Spieltagsdetails."""
    league_name: str
    group_name: str
    year: str
    headers: list[str]
    teams: list[TeamStanding] = field(default_factory=list)
    matchday_dates: dict[str, str] = field(default_factory=dict)
    matchday_venues: dict[str, str] = field(default_factory=dict)
    matchdays_details: dict[str, MatchdayDetail] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# =============================================================================
# Club- & Platznamen-Mapping für offizielle Austragungsorte
# =============================================================================

KNOWN_CLUB_FULL_NAMES = {
    "Royal St. Barbara´s 1": "im Royal St. Barbara's Dortmund Golf Club e.V.",
    "Royal St. Barbara´s": "im Royal St. Barbara's Dortmund Golf Club e.V.",
    "Lippstadt 1": "im Golfclub Lippstadt e.V.",
    "Lippstadt": "im Golfclub Lippstadt e.V.",
    "Münster-Wilkinghege 1": "im Golfclub Münster-Wilkinghege e.V.",
    "Münster-Wilkinghege": "im Golfclub Münster-Wilkinghege e.V.",
    "Mülheim an der Ruhr 1": "im Golfclub Mülheim an der Ruhr e.V.",
    "Mülheim an der Ruhr 2": "im Golfclub Mülheim an der Ruhr e.V.",
    "Mülheim an der Ruhr": "im Golfclub Mülheim an der Ruhr e.V.",
    "Hösel 1": "im Golfclub Hösel e.V.",
    "Hösel 2": "im Golfclub Hösel e.V.",
    "Hösel": "im Golfclub Hösel e.V.",
    "Gelsenkirchen Haus Leythe": "im Gelsenkirchener Golfclub Haus Leythe e.V.",
    "SRS Enterprise 2 (vormals MH-Raffelberg)": "im Golfclub Mülheim-Raffelberg e.V. (SRS Enterprise)",
    "SRS Enterprise 2": "im Golfclub Mülheim-Raffelberg e.V. (SRS Enterprise)",
    "Essen-Heidhausen 2": "im Golfclub Essen-Heidhausen e.V.",
    "Essen-Heidhausen 3": "im Golfclub Essen-Heidhausen e.V.",
    "Essen-Heidhausen": "im Golfclub Essen-Heidhausen e.V.",
    "Duvenhof 2": "im Golf Sport Duvenhof e.V.",
    "Duvenhof": "im Golf Sport Duvenhof e.V.",
    "Niederrh. GC Duisburg": "im Niederrheinischen Golfclub Duisburg e.V.",
    "Golf&more Huckingen": "im Golf & more Duisburg-Huckingen",
    "Velbert Gut Kuhlendahl 3": "im Golfclub Velbert Gut Kuhlendahl e.V.",
    "Bergisch Land 2": "im Golf-Club Bergisch Land Wuppertal e.V.",
    "Westf. GC Gütersloh 1": "im Westfälischer Golf-Club Gütersloh e.V.",
    "Hubbelrath 1": "im Golf Club Hubbelrath e.V.",
    "Bochumer GC 1": "im Bochumer Golfclub e.V.",
    "Kölner GC 1": "im Kölner Golfclub",
    "Krefelder GC 1": "im Krefelder Golf Club e.V.",
    "GSV Düsseldorf 1": "im GSV Golf-Sport-Verein Düsseldorf e.V.",
}


def format_venue_name(raw_host: str) -> str:
    """Formatiert einen Roh-Vereinsnamen in einen sauberen Austragungsort-Text."""
    if not raw_host:
        return ""
    clean = raw_host.strip()
    if clean in KNOWN_CLUB_FULL_NAMES:
        return KNOWN_CLUB_FULL_NAMES[clean]
    if clean.startswith("im "):
        return clean
    # Ohne Ziffer am Ende versuchen
    import re
    no_num = re.sub(r"\s+\d+$", "", clean)
    if no_num in KNOWN_CLUB_FULL_NAMES:
        return KNOWN_CLUB_FULL_NAMES[no_num]
    return f"im {clean}"


# =============================================================================
# Scraper-Klasse
# =============================================================================

class GVNRWScraper:
    """Scraper für GV NRW Golfliga-Ergebnisse mit requests und BeautifulSoup."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })

    # -------------------------------------------------------------------------
    # 1. Download & HTML-Tabellen-Parsing mit BeautifulSoup
    # -------------------------------------------------------------------------

    def fetch_html(self, url: str) -> str:
        """Lädt den HTML-Inhalt einer URL herunter."""
        logger.info(f"Lade HTML von: {url}")
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except requests.RequestException as e:
            logger.error(f"Fehler beim Laden von {url}: {e}")
            raise

    def parse_html_table(
        self,
        html_content: str,
        table_selector: str = "table",
        group_name: str = "AK 50 Herren",
        year: str = "2026",
    ) -> LeagueGroupTable:
        """Parst eine HTML-Tabelle mit BeautifulSoup."""
        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.select_one(table_selector)

        if not table:
            logger.warning(f"Keine Tabelle mit Selektor '{table_selector}' gefunden.")
            return LeagueGroupTable(
                league_name="NRW-MM Herren AK 50",
                group_name=group_name,
                year=year,
                headers=[],
                teams=[],
            )

        headers: list[str] = []
        header_row = table.find("tr")
        if header_row:
            header_cells = header_row.find_all(["th", "td"])
            headers = [
                self._clean_cell_text(c.get_text())
                for c in header_cells
                if self._clean_cell_text(c.get_text())
            ]

        teams: list[TeamStanding] = []
        rows = table.find_all("tr")[1:]

        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            row_values = [self._clean_cell_text(c.get_text()) for c in cells]
            if not any(row_values):
                continue
            standing = self._map_row_to_standing(row_values, headers)
            teams.append(standing)

        return LeagueGroupTable(
            league_name="NRW-MM Herren AK 50",
            group_name=group_name,
            year=year,
            headers=headers,
            teams=teams,
        )

    def _clean_cell_text(self, text: str) -> str:
        return " ".join(text.replace("\xa0", " ").split()).strip()

    def _map_row_to_standing(
        self, values: list[str], headers: list[str], team_id: str = ""
    ) -> TeamStanding:
        rank = values[0] if len(values) > 0 else ""
        club = values[1] if len(values) > 1 else ""

        matchdays: dict[str, str] = {}
        points = ""
        cr_score = ""
        avg_cr = ""

        idx = 2
        while idx < len(values):
            col_name = headers[idx] if idx < len(headers) else f"Spalte_{idx}"
            col_lower = col_name.lower()
            val = values[idx]

            if "spieltag" in col_lower:
                next_val = values[idx + 1] if idx + 1 < len(values) else ""
                next_header = headers[idx + 1].lower() if idx + 1 < len(headers) else ""
                if "punkt" in next_header and next_val:
                    if val and next_val:
                        matchdays[col_name] = f"{val} ({next_val} Pkt)"
                    elif next_val:
                        matchdays[col_name] = f"{next_val} Pkt"
                    else:
                        matchdays[col_name] = val
                    idx += 2
                    continue
                else:
                    matchdays[col_name] = val
            elif "gesamt" in col_lower and "punkte" in col_lower:
                points = val
            elif "punkte" in col_lower and not points:
                points = val
            elif "über cr" in col_lower or "schläge" in col_lower:
                if not cr_score:
                    cr_score = val
                else:
                    avg_cr = val
            elif "ø" in col_lower:
                avg_cr = val

            idx += 1

        if not points and len(values) >= 3:
            points = values[-3] if len(values) >= 3 else values[-1]

        return TeamStanding(
            rank=rank,
            club=club,
            points=points,
            team_id=str(team_id),
            matchdays=matchdays,
            cr_score=cr_score,
            avg_cr=avg_cr,
            raw_data=values,
        )

    # -------------------------------------------------------------------------
    # 2. GV NRW GraphQL API Abfragen
    # -------------------------------------------------------------------------

    def fetch_live_group_table(
        self,
        sub_league_id: str,
        sub_league_name: str,
        year: str = "2026",
    ) -> LeagueGroupTable:
        """Ruft die Live-Tabelle einer Gruppe über das Backend ab."""
        query = """
        query findLeagueResult($leagueId: String!, $subLeagues: [SubLeagueInput]!, $useVisibilty: Boolean) {
          findLeagueResult(input: {
            leagueId: $leagueId, subLeagues: $subLeagues, useVisibilty: $useVisibilty
          }) {
            result {
              name
              spieltage {
                name
                date
                isverified
              }
              teams {
                teamId
                goes_up_down
                data {
                  value
                  homeTeam
                  ltId
                }
              }
            }
          }
        }
        """
        payload = {
            "query": query,
            "variables": {
                "leagueId": str(sub_league_id),
                "subLeagues": [{"leagueId": str(sub_league_id), "name": sub_league_name}],
                "useVisibilty": False,
            },
        }

        res = self.session.post(
            GVNRW_BACKEND_URL, json=payload, timeout=REQUEST_TIMEOUT
        )
        res.raise_for_status()
        data = res.json()
        results = data.get("data", {}).get("findLeagueResult", {}).get("result", [])

        if not results:
            return LeagueGroupTable(
                league_name="NRW-MM Herren AK 50",
                group_name=sub_league_name,
                year=year,
                headers=[],
                teams=[],
            )

        res_group = results[0]
        headers = [col.get("name", "") for col in res_group.get("spieltage", [])]
        matchday_dates = {
            col.get("name", ""): str(col.get("date", "")).split()[0]
            for col in res_group.get("spieltage", [])
            if col.get("date")
        }

        matchday_venues: dict[str, str] = {}
        for col_idx, col in enumerate(res_group.get("spieltage", [])):
            col_name = col.get("name", "")
            if "spieltag" in col_name.lower():
                for team_entry in res_group.get("teams", []):
                    t_data = team_entry.get("data", [])
                    if col_idx < len(t_data):
                        d_item = t_data[col_idx]
                        val_str = str(d_item.get("value", ""))
                        if d_item.get("homeTeam") is True or "**" in val_str or "*" in val_str:
                            club_val = t_data[1].get("value", "") if len(t_data) > 1 else ""
                            if club_val:
                                matchday_venues[col_name] = format_venue_name(club_val)
                            break

        teams: list[TeamStanding] = []
        for team_entry in res_group.get("teams", []):
            raw_values = [d.get("value", "") for d in team_entry.get("data", [])]
            t_id = team_entry.get("teamId", "")
            standing = self._map_row_to_standing(raw_values, headers, team_id=t_id)
            teams.append(standing)

        table = LeagueGroupTable(
            league_name="NRW-MM Herren AK 50",
            group_name=sub_league_name,
            year=year,
            headers=headers,
            teams=teams,
            matchday_dates=matchday_dates,
            matchday_venues=matchday_venues,
        )

        return table

    def fetch_team_player_results(self, team_id: int | str) -> list[dict[str, Any]]:
        """
        Ruft die Spieler-Einzelergebnisse und Platzdaten aller Spieltage
        für ein Team über 'findTeamResult' ab.
        """
        query = """
        query findTeamResult($teamId: Int!) {
          findTeamResult(input: { teamId: $teamId }) {
            spieltage {
              name
              date
              clubname
              tee
              players {
                name
                familyname
                hcp
                playinhcp
                erg_brutto
                plusCR
                pars
                scores
              }
            }
          }
        }
        """
        try:
            res = self.session.post(
                GVNRW_BACKEND_URL,
                json={"query": query, "variables": {"teamId": int(team_id)}},
                timeout=REQUEST_TIMEOUT,
            )
            res.raise_for_status()
            data = res.json()
            return data.get("data", {}).get("findTeamResult", {}).get("spieltage", [])
        except Exception as e:
            logger.warning(f"Konnte Spieler für teamId {team_id} nicht laden: {e}")
            return []

    def build_matchday_details(
        self,
        table: LeagueGroupTable,
        target_team_id: int | str | None = None,
    ) -> dict[str, MatchdayDetail]:
        """Baut für jeden Spieltag die vollständige Detailansicht auf."""
        details: dict[str, MatchdayDetail] = {}

        player_days_map: dict[str, dict[str, Any]] = {}
        if target_team_id:
            raw_days = self.fetch_team_player_results(target_team_id)
            for d in raw_days:
                player_days_map[d.get("name", "").strip()] = d

        spieltage_names = [h for h in table.headers if "spieltag" in h.lower()]

        # Prüfen, welche Spieltage in dieser Gruppe bereits Ergebnisse haben
        day_has_scores: dict[str, bool] = {}
        for day_name in spieltage_names:
            col_idx = table.headers.index(day_name)
            has_sc = any(
                bool(t.raw_data[col_idx].strip())
                for t in table.teams
                if col_idx < len(t.raw_data)
            )
            day_has_scores[day_name] = has_sc

        played_days = [d for d, has_sc in day_has_scores.items() if has_sc]
        canceled_days: list[str] = []
        rescheduled_days: list[str] = []

        for day_name in spieltage_names:
            col_idx = table.headers.index(day_name)
            points_idx = col_idx + 1 if col_idx + 1 < len(table.headers) else None

            team_res_list: list[MatchdayTeamResult] = []
            for t in table.teams:
                if col_idx < len(t.raw_data):
                    raw_score = t.raw_data[col_idx]
                    raw_pts = t.raw_data[points_idx] if points_idx and points_idx < len(t.raw_data) else ""
                    is_home = "**" in raw_score or "*" in raw_score
                    clean_score = raw_score.replace("**", "").replace("*", "").strip()

                    team_res_list.append(
                        MatchdayTeamResult(
                            team_name=t.club,
                            score=clean_score,
                            points=raw_pts,
                            is_home=is_home,
                        )
                    )

            def sort_key(item: MatchdayTeamResult):
                try:
                    pts = float(item.points) if item.points else -1.0
                except ValueError:
                    pts = -1.0
                return -pts

            team_res_list.sort(key=sort_key)
            for r_idx, item in enumerate(team_res_list, 1):
                item.rank = r_idx

            day_player_data = player_days_map.get(day_name, {})
            venue = (day_player_data.get("clubname") or "").strip()
            if not venue:
                venue = table.matchday_venues.get(day_name, "")
            if not venue and "spieltag" in day_name.lower():
                if len(table.teams) == 5 and day_name == "1. Spieltag":
                    venue = "Spielfrei (keine Spielansetzung)"

            tee = (day_player_data.get("tee") or "").strip()
            date_val = table.matchday_dates.get(day_name, "")
            if not date_val and day_player_data.get("date"):
                date_val = str(day_player_data.get("date", "")).split()[0]

            raw_players = day_player_data.get("players") or []
            players_list: list[PlayerScore] = []

            max_plus_cr = -999.0
            worst_player_idx = -1
            has_explicit_streich = False

            for p_idx, p in enumerate(raw_players):
                raw_plus_cr = str(p.get("plusCR") or "")
                raw_brutto = str(p.get("erg_brutto") or "")
                is_streich = "(" in raw_plus_cr or "(" in raw_brutto
                if is_streich:
                    has_explicit_streich = True

                clean_plus_cr = raw_plus_cr.replace("(", "").replace(")", "").replace("+", "").strip()
                clean_brutto = raw_brutto.replace("(", "").replace(")", "").strip()

                try:
                    p_cr_float = float(clean_plus_cr)
                    if p_cr_float > max_plus_cr:
                        max_plus_cr = p_cr_float
                        worst_player_idx = p_idx
                except (ValueError, TypeError):
                    pass

                players_list.append(
                    PlayerScore(
                        name=(p.get("name") or "").strip(),
                        familyname=(p.get("familyname") or "").strip(),
                        hcp=(p.get("hcp") or "").strip(),
                        playinhcp=(p.get("playinhcp") or "").strip(),
                        erg_brutto=clean_brutto,
                        plus_cr=clean_plus_cr,
                        is_streichergebnis=is_streich,
                        pars=p.get("pars") or [],
                        scores=p.get("scores") or [],
                    )
                )

            if not has_explicit_streich and len(players_list) >= 6 and worst_player_idx >= 0:
                players_list[worst_player_idx].is_streichergebnis = True

            # Dynamische Prüfung auf Ausfall / Nachholtermin / Geplant
            has_sc = day_has_scores.get(day_name, False) or len(players_list) > 0
            is_canceled = False
            is_rescheduled = False
            status_note = ""

            if not played_days:
                # Saison hat noch nicht begonnen (z. B. 2027)
                status_note = "Ausstehend (Saison noch nicht gestartet)"
            elif not has_sc:
                # Wurde bereits ein späterer Spieltag gespielt oder liegt das Datum vor dem letzten gespielten Tag?
                later_played = any(
                    day_has_scores.get(later_name, False)
                    for later_name in spieltage_names[spieltage_names.index(day_name) + 1:]
                )
                day_date = date_val or table.matchday_dates.get(day_name, "")
                latest_played_date = max((table.matchday_dates.get(p, "") for p in played_days), default="")
                is_past = bool(day_date and latest_played_date and day_date < latest_played_date)

                if later_played or is_past:
                    is_canceled = True
                    status_note = "Ausgefallen / Nicht ausgetragen"
                    canceled_days.append(day_name)
                else:
                    status_note = "Ausstehend"
            else:
                try:
                    current_day_num = int("".join(filter(str.isdigit, day_name)))
                    for prev_day_name in spieltage_names[:spieltage_names.index(day_name)]:
                        if day_has_scores.get(prev_day_name, False):
                            prev_num = int("".join(filter(str.isdigit, prev_day_name)))
                            if prev_num > current_day_num:
                                is_rescheduled = True
                                status_note = f"Nachholtermin (ausgetragen nach {prev_num}. Spieltag)"
                                rescheduled_days.append(day_name)
                                break
                except (ValueError, TypeError):
                    pass

            details[day_name] = MatchdayDetail(
                day_name=day_name,
                date=date_val,
                venue=venue,
                tee_info=tee,
                team_results=team_res_list,
                players=players_list,
                is_canceled=is_canceled,
                is_rescheduled=is_rescheduled,
                status_note=status_note,
            )

        # Verknüpfung zwischen ausgefallenen und nachgeholten Spieltagen herstellen
        for c_day, r_day in zip(canceled_days, rescheduled_days):
            if c_day in details and r_day in details:
                details[c_day].linked_rescheduled_day = r_day
                details[r_day].linked_canceled_day = c_day

                # Ergebnisse und Spieler des Nachholspieltags auf den ausgefallenen Tag übertragen,
                # damit der Spieltag nicht leer bleibt, sondern die nachgeholten Daten zeigt:
                r_det = details[r_day]
                if not details[c_day].venue:
                    details[c_day].venue = f"{r_det.venue} (Nachholtermin am {r_det.date})"
                if not details[c_day].tee_info:
                    details[c_day].tee_info = r_det.tee_info
                if not details[c_day].team_results or all(not tr.score for tr in details[c_day].team_results):
                    details[c_day].team_results = r_det.team_results
                if not details[c_day].players:
                    details[c_day].players = r_det.players

                # Auch in team.matchdays des Spieltags eintragen
                for t in table.teams:
                    if not t.matchdays.get(c_day) and t.matchdays.get(r_day):
                        t.matchdays[c_day] = f"{t.matchdays[r_day]} [Nachholer]"

        return details

    # -------------------------------------------------------------------------
    # 3. Kompletter Datensatz für Mülheim 1 & 2 (Mehrjahres-Daten)
    # -------------------------------------------------------------------------

    def fetch_complete_muelheim_dataset(
        self,
        years: list[str] | None = None,
    ) -> dict[str, Any]:
        """Lädt Daten für GC Mülheim 1 und 2 für die angegebenen Jahre."""
        if years is None:
            years = ["2024", "2025", "2026", "2027"]

        dataset: dict[str, Any] = {}

        for year in years:
            dataset[year] = {}
            mapping_for_year = KNOWN_MUELHEIM_GROUPS.get(year, {})

            for team_key in ["1", "2"]:
                team_name = f"GC Mülheim {team_key}"
                group_info = mapping_for_year.get(team_key)

                if not group_info:
                    continue

                logger.info(
                    f"Lade Saison {year} für {team_name} ({group_info['group_name']})..."
                )

                table = self.fetch_live_group_table(
                    sub_league_id=group_info["league_id"],
                    sub_league_name=group_info["group_name"],
                    year=year,
                )

                team_id = group_info.get("team_id")
                details = self.build_matchday_details(table, target_team_id=team_id)
                table.matchdays_details = details

                dataset[year][team_key] = table.to_dict()

        return dataset

    # -------------------------------------------------------------------------
    # 4. Generierung von 'ergebnisse.html' mit Tailwind CSS via CDN
    # -------------------------------------------------------------------------

    def generate_interactive_mobile_html(
        self,
        dataset: dict[str, Any],
        filepath: str | Path = "ergebnisse.html",
        timestamp: str | None = None,
    ) -> None:
        """
        Erstellt eine moderne, mobil-optimierte HTML-Datei mit Tailwind CSS
        via CDN, strikter Content Security Policy (CSP), sauberem Tabellenlayout
        und ausgelagerter Anwendungslogik in 'app.js'.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not timestamp:
            timestamp = datetime.now().strftime("%d.%m.%Y, %H:%M Uhr")

        logo_path = Path("GCMH_Logo_rund_freigestellt.png")
        if not logo_path.exists():
            candidate = Path(__file__).parent / "GCMH_Logo_rund_freigestellt.png"
            if candidate.exists():
                logo_path = candidate

        if logo_path.exists():
            import base64
            logo_b64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
            logo_data_uri = f"data:image/png;base64,{logo_b64}"
        else:
            logo_data_uri = "GCMH_Logo_rund_freigestellt.png"

        json_data_str = json.dumps(dataset, ensure_ascii=False)
        escaped_json_str = json_data_str.replace("</", "<\\/")

        html_content = f"""<!DOCTYPE html>
<html lang="de" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self'; object-src 'none'; base-uri 'self';">
    <!-- PWA & Mobile Web App Meta-Tags -->
    <meta name="theme-color" content="#006eb7">
    <meta name="msapplication-navbutton-color" content="#006eb7">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="AK 50 Golf">
    <link rel="manifest" href="manifest.json">
    <link rel="apple-touch-icon" href="icon-192.png">
    <link rel="icon" type="image/png" href="icon-192.png">
    <title>GV NRW - AK 50 Herren | GC Mülheim an der Ruhr</title>
    <!-- Tailwind CSS via CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Externe Anwendungslogik & Event-Handler (ohne inline-scripts für strikte CSP) -->
    <script src="app.js" defer></script>
    <style>
        html {{
            background-color: #006eb7;
        }}
        body {{
            padding-bottom: env(safe-area-inset-bottom, 2.5rem);
            -webkit-tap-highlight-color: transparent;
        }}
    </style>
</head>
<body class="bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 min-h-full font-sans antialiased pb-10">

    <div class="max-w-xl mx-auto px-3 py-3 sm:px-4">

        <!-- Top Timestamp Banner -->
        <div class="flex items-center justify-between text-[11px] text-slate-600 dark:text-slate-300 bg-white/90 dark:bg-slate-800/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 mb-2.5 shadow-2xs">
            <div class="flex items-center gap-1.5">
                <span class="relative flex h-2 w-2">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2 bg-sky-500"></span>
                </span>
                <span>Letztes Update: <strong class="text-slate-900 dark:text-white font-semibold">{timestamp}</strong></span>
            </div>
            <span class="px-2 py-0.2 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-900 dark:bg-blue-950/80 dark:text-sky-300 border border-blue-200/80 dark:border-blue-800/60">
                GV NRW
            </span>
        </div>

        <!-- Header with GC Mülheim Logo (Clean White Style) -->
        <header class="bg-white dark:bg-slate-800 rounded-xl p-3 sm:p-3.5 mb-2.5 shadow-2xs border border-slate-200 dark:border-slate-700">
            <div class="flex justify-between items-center gap-2">
                <div class="flex items-center gap-2.5 min-w-0">
                    <div class="w-12 h-12 sm:w-14 sm:h-14 shrink-0 flex items-center justify-center -translate-y-0.5 sm:-translate-y-1">
                        <img src="{logo_data_uri}" alt="GC Mülheim Logo" class="w-full h-full object-contain filter drop-shadow-2xs" />
                    </div>
                    <div class="min-w-0">
                        <div class="flex items-center gap-1.5 flex-wrap">
                            <span class="text-[10px] font-extrabold uppercase tracking-widest text-blue-700 dark:text-sky-400">GC Mülheim an der Ruhr</span>
                        </div>
                        <h1 class="text-base sm:text-lg font-black tracking-tight text-slate-900 dark:text-white leading-tight truncate">GV NRW &bull; AK 50 Herren</h1>
                        <p id="subHeaderDesc" class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 font-medium truncate">Ligatabellen &amp; Spieltage &bull; GC Mülheim</p>
                    </div>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                    <button id="openShareBtn" title="Seite oder Ansicht teilen" class="bg-blue-50 hover:bg-blue-100 dark:bg-slate-700/80 dark:hover:bg-slate-700 active:scale-95 text-blue-700 dark:text-sky-300 text-xs px-2.5 py-1.5 rounded-lg font-semibold border border-blue-200/80 dark:border-slate-600 flex items-center gap-1.5 transition-all shadow-2xs cursor-pointer">
                        <svg class="w-3.5 h-3.5 text-blue-600 dark:text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"></path>
                        </svg>
                        <span>Teilen</span>
                    </button>
                    <div class="bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 text-[11px] px-2 py-1.5 rounded-md font-medium border border-slate-200 dark:border-slate-600 hidden sm:block">
                        Liga-Portal
                    </div>
                </div>
            </div>
        </header>

        <!-- Controls: Season Year & Team Selector -->
        <div class="bg-white dark:bg-slate-800 rounded-xl p-2.5 border border-slate-200 dark:border-slate-700 mb-2.5 shadow-2xs space-y-2">
            <div>
                <span class="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Saison / Jahr</span>
                <div class="grid grid-cols-4 gap-1 bg-slate-100 dark:bg-slate-900/60 p-0.5 rounded-lg" id="yearSelector">
                    <button class="py-1.5 text-xs font-semibold rounded-md text-slate-600 dark:text-slate-300 transition-all text-center hover:text-slate-900 dark:hover:text-white" data-year="2024">2024</button>
                    <button class="py-1.5 text-xs font-semibold rounded-md text-slate-600 dark:text-slate-300 transition-all text-center hover:text-slate-900 dark:hover:text-white" data-year="2025">2025</button>
                    <button class="py-1.5 text-xs font-semibold rounded-md bg-white dark:bg-slate-800 text-blue-700 dark:text-sky-400 shadow-2xs font-bold transition-all text-center" data-year="2026">2026</button>
                    <button class="py-1.5 text-xs font-semibold rounded-md text-slate-600 dark:text-slate-300 transition-all text-center hover:text-slate-900 dark:hover:text-white" data-year="2027">2027</button>
                </div>
            </div>
            <div>
                <span class="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Mannschaft</span>
                <div class="grid grid-cols-2 gap-1.5 bg-slate-100 dark:bg-slate-900/60 p-0.5 rounded-lg" id="teamSelector">
                    <button class="py-1.5 px-2.5 text-xs rounded-md bg-white dark:bg-slate-800 text-blue-700 dark:text-sky-400 shadow-2xs font-bold transition-all flex items-center justify-center gap-1.5" data-team="1">⛳ GC Mülheim 1</button>
                    <button class="py-1.5 px-2.5 text-xs rounded-md text-slate-600 dark:text-slate-300 font-semibold transition-all flex items-center justify-center gap-1.5 hover:text-slate-900 dark:hover:text-white" data-team="2">⛳ GC Mülheim 2</button>
                </div>
            </div>
        </div>

        <!-- Active League Title & Rank Badge -->
        <div class="flex items-center justify-between bg-white dark:bg-slate-800 p-2.5 sm:p-3 rounded-xl border border-slate-200 dark:border-slate-700 mb-2.5 shadow-2xs">
            <div>
                <h2 id="leagueGroupTitle" class="text-sm sm:text-base font-bold text-slate-900 dark:text-white">Liga 2.A (2026)</h2>
                <span id="leagueSubtitle" class="text-[11px] text-slate-500 dark:text-slate-400">NRW-Mannschaftsmeisterschaft Herren AK 50</span>
            </div>
            <span id="myRankBadge" class="bg-blue-100 text-blue-900 dark:bg-blue-950/80 dark:text-sky-300 px-2.5 py-0.5 rounded-full text-xs font-bold border border-blue-200/80 dark:border-blue-800/60">
                Rang #3
            </span>
        </div>

        <!-- Standings Table (Clean Layout with Alternating Rows) -->
        <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden mb-3.5 shadow-2xs">
            <div class="px-3 py-2 bg-slate-50 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-700 flex justify-between items-center">
                <div class="flex items-center gap-2">
                    <span class="text-[11px] font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">Aktuelle Ligatabelle</span>
                    <span id="seasonPointsTag" class="text-xs font-bold text-blue-700 dark:text-sky-400"></span>
                </div>
                <button id="toggleAllBtn" class="text-[10px] font-semibold text-blue-700 dark:text-sky-400 hover:text-blue-800 dark:hover:text-sky-300 flex items-center gap-1 bg-white dark:bg-slate-700 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-600 shadow-2xs transition-colors">
                    <span>Spieltage</span> <span>▾</span>
                </button>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                    <thead class="bg-slate-100 dark:bg-slate-900/60 text-slate-500 dark:text-slate-400 uppercase text-[10px] font-semibold border-b border-slate-200 dark:border-slate-700">
                        <tr>
                            <th class="py-1.5 px-2 text-center w-9">#</th>
                            <th class="py-1.5 px-2.5">Club</th>
                            <th class="py-1.5 px-2.5 text-right">Punkte</th>
                            <th class="py-1.5 px-2.5 text-right">Ø über CR</th>
                        </tr>
                    </thead>
                    <tbody id="standingsTableBody" class="divide-y divide-slate-100 dark:divide-slate-700/60">
                        <!-- Dynamisch generiert -->
                    </tbody>
                </table>
            </div>
            <div id="tableNoticeContainer"></div>
        </div>

        <!-- Matchdays Grid Section -->
        <div class="flex items-center justify-between mb-2 px-1">
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">Spieltage &amp; Ergebnisse</h3>
            <span class="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1">👉 Tippen für Spielerdetails</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2" id="matchdaysGrid">
            <!-- Dynamisch generiert -->
        </div>

        <!-- Modal Dialog for Matchday Details -->
        <div class="fixed inset-0 z-50 hidden items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-xs" id="detailModal">
            <div class="bg-white dark:bg-slate-800 w-full max-w-xl rounded-t-3xl sm:rounded-2xl max-h-[90vh] overflow-y-auto p-4 sm:p-6 shadow-2xl transition-all">
                <div class="flex justify-between items-start pb-3 border-b border-slate-200 dark:border-slate-700 mb-3">
                    <div>
                        <h3 id="modalDayTitle" class="text-lg font-extrabold text-slate-900 dark:text-white">1. Spieltag</h3>
                        <p id="modalDayDate" class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Datum: 25.04.2026</p>
                    </div>
                    <button id="closeDetailModalBtn" class="bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white rounded-full w-8 h-8 flex items-center justify-center font-bold text-sm">✕</button>
                </div>

                <div id="modalBannerContainer"></div>

                <div class="bg-slate-50 dark:bg-slate-900/60 p-3 rounded-xl text-xs text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 mb-3 space-y-1" id="modalVenueBox">
                    <div>Austragungsort: <strong id="modalVenueText" class="text-slate-900 dark:text-white">-</strong></div>
                    <div id="modalTeeRow">Platzdaten: <strong id="modalTeeText" class="text-slate-900 dark:text-white">-</strong></div>
                </div>

                <!-- Modal Navigation Tabs -->
                <div class="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 dark:bg-slate-900/60 rounded-xl mb-3.5">
                    <button class="py-2 px-2 text-xs font-semibold rounded-lg bg-blue-700 text-white shadow-xs transition-all text-center" id="tabBtnTeams">
                        🏆 Mannschaftswertung
                    </button>
                    <button class="py-2 px-2 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-300 transition-all text-center" id="tabBtnPlayers">
                        👤 Einzelspieler (Mülheim)
                    </button>
                </div>

                <!-- Tab Content 1: Team Results -->
                <div id="tabContentTeams">
                    <div class="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
                        <table class="w-full text-left text-xs divide-y divide-slate-200 dark:divide-slate-700">
                            <thead class="bg-slate-100 dark:bg-slate-900/60 text-slate-500 dark:text-slate-400 uppercase text-[10px] font-semibold">
                                <tr>
                                    <th class="py-2 px-2.5 text-center w-8">Rang</th>
                                    <th class="py-2 px-2.5">Mannschaft</th>
                                    <th class="py-2 px-2.5 text-right">Schläge &gt; CR</th>
                                    <th class="py-2 px-2.5 text-right">Punkte</th>
                                </tr>
                            </thead>
                            <tbody id="modalTeamResultsBody" class="divide-y divide-slate-100 dark:divide-slate-700/60">
                                <!-- Dynamisch generiert -->
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Tab Content 2: Player Results -->
                <div id="tabContentPlayers" class="hidden space-y-2">
                    <div id="modalPlayersList" class="space-y-2">
                        <!-- Dynamisch generiert -->
                    </div>
                </div>
            </div>
        </div>

        <!-- Share Modal Dialog -->
        <div class="fixed inset-0 z-50 hidden items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-xs" id="shareModal">
            <div class="bg-white dark:bg-slate-800 w-full max-w-sm rounded-t-2xl sm:rounded-xl max-h-[90vh] overflow-y-auto p-4 shadow-2xl transition-all">
                <div class="flex justify-between items-start pb-2 border-b border-slate-200 dark:border-slate-700 mb-3">
                    <div>
                        <h3 class="text-sm font-extrabold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <span>🔗</span> <span>Ansicht teilen</span>
                        </h3>
                        <p id="shareModalSubtitle" class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">GC Mülheim 1 • Saison 2026</p>
                    </div>
                    <button id="closeShareModalBtn" class="bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white rounded-full w-6 h-6 flex items-center justify-center font-bold text-xs">✕</button>
                </div>

                <div class="space-y-2.5">
                    <!-- Share URL input & copy button -->
                    <div>
                        <label class="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Link zum Teilen</label>
                        <div class="flex items-center gap-1.5">
                            <input type="text" id="shareUrlInput" readonly class="w-full text-xs bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-800 dark:text-slate-200 font-mono select-all focus:outline-none" />
                            <button id="copyShareBtn" class="shrink-0 bg-blue-700 hover:bg-blue-800 active:scale-95 text-white text-xs font-bold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1">
                                <span>Kopieren</span>
                            </button>
                        </div>
                    </div>

                    <!-- Direct Sharing Channels -->
                    <div class="pt-1 space-y-1.5">
                        <span class="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Direkt senden</span>
                        <div class="grid grid-cols-2 gap-2">
                            <button id="shareWhatsAppBtn" class="w-full bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white text-xs font-bold py-2 px-3 rounded-lg flex items-center justify-center gap-1.5 transition-all shadow-2xs">
                                <span>💬</span> <span>WhatsApp</span>
                            </button>
                            <button id="shareEmailBtn" class="w-full bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-xs font-bold py-2 px-3 rounded-lg flex items-center justify-center gap-1.5 transition-all shadow-2xs">
                                <span>✉️</span> <span>E-Mail</span>
                            </button>
                        </div>
                        <button id="systemShareBtn" class="w-full bg-slate-100 dark:bg-slate-700/80 hover:bg-slate-200 dark:hover:bg-slate-700 active:scale-95 text-slate-700 dark:text-slate-200 text-xs font-semibold py-1.5 px-3 rounded-lg flex items-center justify-center gap-1.5 transition-all">
                            <span>📲</span> <span>System-Teilen</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <footer class="text-center text-xs text-slate-400 dark:text-slate-500 mt-6 pt-4 border-t border-slate-200/60 dark:border-slate-800">
            Datenquelle: Golfverband NRW (GV NRW) &bull; Mobil-optimierte Ansicht
        </footer>

    </div>

    <!-- Toast Notification for Share / Clipboard -->
    <div id="toastNotification" class="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-50 pointer-events-none transition-all duration-300 opacity-0 translate-y-3">
        <div class="bg-slate-900/90 dark:bg-blue-950/90 text-white text-xs font-semibold px-4 py-2 rounded-full shadow-lg backdrop-blur-md border border-slate-700 dark:border-blue-700/60 flex items-center gap-2">
            <span id="toastIcon">📋</span>
            <span id="toastMessage">Link in die Zwischenablage kopiert!</span>
        </div>
    </div>

    <!-- Embedded Scraped Data (JSON) -->
    <script id="golf-data" type="application/json">
{escaped_json_str}
    </script>
</body>
</html>
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Moderne Web-App erfolgreich generiert: {path}")

        # Generiere auch die zugehörige app.js im selben Verzeichnis
        base_dir = path.parent if path.parent.is_dir() else Path(".")
        generate_app_js(base_dir)


def generate_app_js(output_dir: Path | str = ".") -> Path:
    """
    Erzeugt die externe JavaScript-Datei 'app.js' für ergebnisse.html.
    Enthält die gesamte Anwendungslogik mit sicherem DOM-Rendering (textContent,
    document.createElement, Priorität 2), Event-Listenern (keine inline-onclick)
    sowie die Tailwind-CSS-Farbkonfiguration für strikte CSP-Konformität.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    app_file = out_path / "app.js"

    app_code = """// =============================================================================
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
"""
    app_file.write_text(app_code.strip() + "\n", encoding="utf-8")
    logger.info(f"App-Logik (app.js) generiert: {app_file}")
    return app_file



# =============================================================================
# CLI
# =============================================================================

def parse_args(args: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description="GV NRW AK 50 Herren Scraper mit Mülheim 1 & 2 und Spielerdetails"
    )
    parser.add_argument(
        "--year",
        default="2026",
        help="Saisonjahr (2024, 2025, 2026, 2027) - Standard: 2026",
    )
    parser.add_argument(
        "--team",
        default="1",
        choices=["1", "2"],
        help="Mannschaft: 1 (GC Mülheim 1) oder 2 (GC Mülheim 2)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Erzwingt Aktualisierung und Deployment auf GitHub Pages, auch wenn der Daten-Hash unverändert ist",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Nur lokale Ausführung: Aktualisiert HTML, PWA und app.js lokal ohne GitHub Pages Deployment",
    )
    return parser.parse_args(args)


# =============================================================================
# PWA (Progressive Web App) Generator Funktionen
# =============================================================================

def create_golf_icon_png(size: int = 192, antialias: bool = True) -> bytes:
    """
    Erzeugt ein Golf-App-Icon im PNG-Format mit reinem Python (zlib, struct, math),
    ohne externe Abhängigkeiten wie Pillow.
    Vereinsblau-Hintergrund (#006eb7), weiße Konturen/Golf-Symbol (Fahne, Loch, Ball, Ring).
    """
    bg = (0, 110, 183)  # #006eb7 (GC Mülheim Vereinsblau)
    fg = (255, 255, 255)

    subsamples = [(-0.25, -0.25), (0.25, -0.25), (-0.25, 0.25), (0.25, 0.25)] if antialias else [(0.0, 0.0)]
    num_samples = len(subsamples)
    inv_size = 1.0 / size

    def test_point(nx: float, ny: float) -> bool:
        # Kreisring / Emblem
        dx = nx - 0.5
        dy = ny - 0.5
        dist_center = math.sqrt(dx * dx + dy * dy)
        if 0.435 <= dist_center <= 0.455:
            return True

        # Fahnenstange: Vertikale Linie bei nx=0.38
        if (abs(nx - 0.38) <= 0.012) and (0.22 <= ny <= 0.74):
            return True

        # Fahnentuch: Dreieck von nx=0.38 bis nx=0.68
        if 0.38 <= nx <= 0.68:
            t = (nx - 0.38) / 0.30
            top_y = 0.22 + 0.11 * t
            bot_y = 0.44 - 0.11 * t
            if top_y <= ny <= bot_y:
                return True

        # Loch / Grün-Basis: Ellipse am Stangenfuß
        dx_b = (nx - 0.38) / 0.11
        dy_b = (ny - 0.74) / 0.025
        if dx_b * dx_b + dy_b * dy_b <= 1.0:
            return True

        # Golfball: Weißer Kreis bei (0.60, 0.70)
        dx_ball = (nx - 0.60) / 0.075
        dy_ball = (ny - 0.70) / 0.075
        if dx_ball * dx_ball + dy_ball * dy_ball <= 1.0:
            return True

        return False

    raw_bytes = bytearray()
    for y in range(size):
        raw_bytes.append(0)  # Filter byte: 0 (None)
        for x in range(size):
            hits = 0
            for sx, sy in subsamples:
                nx = (x + 0.5 + sx) * inv_size
                ny = (y + 0.5 + sy) * inv_size
                if test_point(nx, ny):
                    hits += 1
            if hits == 0:
                raw_bytes.extend(bg)
            elif hits == num_samples:
                raw_bytes.extend(fg)
            else:
                alpha = hits / num_samples
                r = int(bg[0] * (1.0 - alpha) + fg[0] * alpha)
                g = int(bg[1] * (1.0 - alpha) + fg[1] * alpha)
                b = int(bg[2] * (1.0 - alpha) + fg[2] * alpha)
                raw_bytes.extend((r, g, b))

    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        content = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(content) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + content + crc

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = make_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    idat = make_chunk(b"IDAT", zlib.compress(bytes(raw_bytes), 9))
    iend = make_chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def generate_pwa_icons(output_dir: Path | str = ".", force: bool = False) -> dict[str, Path]:
    """
    Stellt die PWA-Icons icon-192.png und icon-512.png im Zielordner bereit.
    Nutzt vorrangig die echten Vereinslogo-Icons aus dem Projektordner.
    Falls sie bereits existieren und force=False ist, bleiben sie erhalten.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    icon_192_path = out_path / "icon-192.png"
    icon_512_path = out_path / "icon-512.png"

    proj_192 = Path("icon-192.png")
    proj_512 = Path("icon-512.png")

    if force or not icon_192_path.exists() or icon_192_path.stat().st_size == 0:
        if proj_192.exists() and proj_192.resolve() != icon_192_path.resolve() and proj_192.stat().st_size > 0:
            icon_192_path.write_bytes(proj_192.read_bytes())
            logger.info(f"PWA-Vereins-Icon übernommen: {icon_192_path} (192x192)")
        else:
            icon_192_path.write_bytes(create_golf_icon_png(192))
            logger.info(f"PWA-Icon generiert: {icon_192_path} (192x192)")

    if force or not icon_512_path.exists() or icon_512_path.stat().st_size == 0:
        if proj_512.exists() and proj_512.resolve() != icon_512_path.resolve() and proj_512.stat().st_size > 0:
            icon_512_path.write_bytes(proj_512.read_bytes())
            logger.info(f"PWA-Vereins-Icon übernommen: {icon_512_path} (512x512)")
        else:
            icon_512_path.write_bytes(create_golf_icon_png(512))
            logger.info(f"PWA-Icon generiert: {icon_512_path} (512x512)")

    return {"icon-192": icon_192_path, "icon-512": icon_512_path}


def generate_pwa_manifest(output_dir: Path | str = ".") -> Path:
    """
    Erzeugt die Web App Manifest-Datei (manifest.json).
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest_file = out_path / "manifest.json"

    manifest_data = {
        "name": "GC Mülheim AK 50",
        "short_name": "AK 50 Golf",
        "description": "Ergebnisse, Spieltage & Scorekarten AK 50 Herren GC Mülheim",
        "start_url": "./index.html",
        "scope": "./",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#ffffff",
        "theme_color": "#006eb7",
        "icons": [
            {
                "src": "icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": "icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
    }

    manifest_file.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"PWA-Manifest generiert: {manifest_file}")
    return manifest_file


def generate_pwa_service_worker(output_dir: Path | str = ".") -> Path:
    """
    Erzeugt die Service Worker-Datei (sw.js) mit Network-First-Strategie.
    Aktuelle Daten werden online stets live vom Netlify-Server bezogen.
    Nur bei Verbindungsabbruch / Offline wird auf den Cache zurückgegriffen.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    sw_file = out_path / "sw.js"

    sw_code = """// Service Worker für GC Mülheim AK 50 PWA
// Strategie: Network-First (immer frische Daten aus dem Netz, Cache als Offline-Fallback)

const CACHE_NAME = 'gcmh-ak50-v6';
const ASSETS_TO_CACHE = [
    './',
    './index.html',
    './ergebnisse.html',
    './app.js',
    './manifest.json',
    './icon-192.png',
    './icon-512.png'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
                console.warn('[SW] Vorab-Caching Warnung:', err);
            });
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

// Network-First Strategie: Online immer neueste Netlify-Ergebnisse laden
self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    event.respondWith(
        fetch(event.request)
            .then((networkResponse) => {
                if (networkResponse && networkResponse.status === 200) {
                    const responseClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return networkResponse;
            })
            .catch(() => {
                return caches.match(event.request).then((cachedResponse) => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    if (event.request.mode === 'navigate') {
                        return caches.match('./index.html') || caches.match('./ergebnisse.html');
                    }
                });
            })
    );
});
"""
    sw_file.write_text(sw_code.strip() + "\n", encoding="utf-8")
    logger.info(f"PWA-Service-Worker generiert: {sw_file}")
    return sw_file


def generate_pwa_files(output_dir: Path | str = ".") -> dict[str, Path]:
    """
    Stellt sicher, dass alle PWA-Komponenten (app.js, Icons, manifest.json, sw.js)
    im Zielverzeichnis existieren.
    """
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    app_js = generate_app_js(target)
    icons = generate_pwa_icons(target)
    manifest = generate_pwa_manifest(target)
    sw = generate_pwa_service_worker(target)

    return {
        "app_js": app_js,
        "icon-192": icons["icon-192"],
        "icon-512": icons["icon-512"],
        "manifest": manifest,
        "sw": sw,
    }


def compute_data_hash(data: Any) -> str:
    """
    Berechnet einen deterministischen SHA-256 Hash über das serialisierte Daten-Dictionary
    (sort_keys=True), um inhaltliche Änderungen der Ligadaten zuverlässig zu erkennen.
    """
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def deploy_to_github(
    html_path: Path | str = "ergebnisse.html",
    token: str = GITHUB_TOKEN,
    user: str = GITHUB_USER,
    repo: str = GITHUB_REPO,
    branch: str = "main",
) -> dict[str, Any] | None:
    """
    Lädt die Web-App-Dateien für GitHub Pages per GitHub REST API (PUT /repos/{user}/{repo}/contents/{path})
    in den Branch 'main' hoch.

    Zu übertragende Dateien:
    - ergebnisse.html (als index.html für GitHub Pages Root)
    - manifest.json
    - sw.js
    - icon-192.png
    - icon-512.png

    Vor jedem Upload wird ein GET auf die GitHub REST API ausgeführt, um den SHA-Hash
    bereits existierender Dateien abzufragen (erforderlich für Updates).
    Entspricht der SHA-Wert auf GitHub exakt dem lokalen Git-Blob-SHA, wird der Upload
    übersprungen, um redundante Commits zu vermeiden.
    """
    if not token:
        print("\n[-] GitHub-Deployment Fehler: Kein GITHUB_TOKEN in .env gefunden.")
        return None

    if not user or not repo:
        print("\n[!] GitHub-Deployment übersprungen: Bitte konfiguriere GITHUB_USER und GITHUB_REPO.")
        return None

    path = Path(html_path)
    if not path.exists():
        print(f"\n[-] GitHub-Deployment Fehler: Datei '{path}' nicht gefunden.")
        return None

    print(f"\n[+] Starte GitHub Pages Deployment auf {user}/{repo} (Branch: {branch})...")

    base_dir = path.parent if path.parent.is_dir() else Path(".")

    # PWA-Dateien sicherstellen
    generate_pwa_files(base_dir)

    upload_map: dict[str, Path] = {
        "index.html": path,
        "app.js": base_dir / "app.js",
        "manifest.json": base_dir / "manifest.json",
        "sw.js": base_dir / "sw.js",
        "icon-192.png": base_dir / "icon-192.png",
        "icon-512.png": base_dir / "icon-512.png",
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": user or "GVNRW-Scraper",
    }

    uploaded_files: dict[str, Any] = {}
    has_errors = False

    for remote_name, local_file in upload_map.items():
        if not local_file.exists():
            fallback = Path(local_file.name)
            if fallback.exists():
                local_file = fallback
            else:
                print(f"    [-] Datei '{local_file}' nicht gefunden, überspringe...")
                has_errors = True
                continue

        raw_bytes = local_file.read_bytes()
        # Git-Blob-SHA berechnen: sha1("blob <size>\0<bytes>")
        git_blob_sha = hashlib.sha1(
            f"blob {len(raw_bytes)}\0".encode("ascii") + raw_bytes
        ).hexdigest()

        # 1. GET auf GitHub Contents API, um bestehenden SHA zu ermitteln
        api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{remote_name}?ref={branch}"
        existing_sha = None

        try:
            get_res = requests.get(api_url, headers=headers, timeout=20)
            if get_res.status_code == 200:
                existing_sha = get_res.json().get("sha")
            elif get_res.status_code != 404:
                print(f"    [!] Hinweis bei GET {remote_name}: HTTP {get_res.status_code}")
        except Exception as e:
            print(f"    [-] Fehler beim Abfragen von {remote_name}: {e}")
            has_errors = True
            continue

        # Wenn der Hash auf GitHub identisch ist, Upload überspringen
        if existing_sha and existing_sha == git_blob_sha:
            print(f"    * {remote_name}: Bereits aktuell auf GitHub ({existing_sha[:7]}), kein Upload nötig.")
            uploaded_files[remote_name] = {"sha": existing_sha, "status": "unchanged"}
            continue

        # 2. PUT auf GitHub Contents API
        put_url = f"https://api.github.com/repos/{user}/{repo}/contents/{remote_name}"
        b64_content = base64.b64encode(raw_bytes).decode("ascii")
        commit_message = (
            f"Update {remote_name} via GV NRW Scraper"
            if existing_sha
            else f"Add {remote_name} via GV NRW Scraper"
        )
        payload: dict[str, Any] = {
            "message": commit_message,
            "content": b64_content,
            "branch": branch,
        }
        if existing_sha:
            payload["sha"] = existing_sha

        try:
            put_res = requests.put(put_url, headers=headers, json=payload, timeout=30)
            if put_res.status_code in (200, 201):
                res_data = put_res.json()
                new_commit_sha = (
                    res_data.get("commit", {}).get("sha", "")[:7]
                    or res_data.get("content", {}).get("sha", "")[:7]
                )
                action = "aktualisiert" if put_res.status_code == 200 else "erstellt"
                print(f"    * {remote_name}: Erfolgreich {action} (Commit: {new_commit_sha})")
                uploaded_files[remote_name] = {
                    "sha": res_data.get("content", {}).get("sha"),
                    "commit": new_commit_sha,
                    "status": action,
                }
            else:
                has_errors = True
                print(f"    [-] Fehler beim Upload von {remote_name}: HTTP {put_res.status_code}")
                try:
                    err_detail = put_res.json().get("message", put_res.text)
                    print(f"        Detail: {err_detail}")
                except Exception:
                    print(f"        Detail: {put_res.text}")
        except Exception as e:
            has_errors = True
            print(f"    [-] Verbindungsfehler bei Upload von {remote_name}: {e}")

    live_url = f"https://{user}.github.io/{repo}/"
    if not has_errors and uploaded_files:
        print("====================================================================")
        print("🚀 GitHub Pages Deployment ERFOLGREICH!")
        print(f"Öffentlicher Weblink: {live_url}")
        print("====================================================================")
        return {
            "url": live_url,
            "files": uploaded_files,
        }
    elif uploaded_files:
        print(f"[!] GitHub Pages Deployment mit Teil-Erfolg abgeschlossen: {live_url}")
        return {
            "url": live_url,
            "files": uploaded_files,
        }
    else:
        print("[-] GitHub Pages Deployment fehlgeschlagen.")
        return None


def main():
    args = parse_args()
    force_deploy = bool(getattr(args, "force", False) or "--force" in sys.argv)
    is_local = bool(getattr(args, "local", False) or "--local" in sys.argv)

    scraper = GVNRWScraper()

    print("=" * 68)
    print("Golfverband NRW (GV NRW) - AK 50 Herren Scraper")
    print("Interaktive Ansicht für GC Mülheim 1 & GC Mülheim 2")
    print("=" * 68)

    # Prüfe auf bestehenden Deploy-Hash
    hash_file = Path(".last_deploy_hash")
    last_deploy_hash = None
    if hash_file.exists():
        try:
            last_deploy_hash = hash_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning(f"Konnte .last_deploy_hash nicht lesen: {e}")

    json_path = Path("data_muelheim.json")
    print("\n[+] Lade vollständigen Datensatz (2024 - 2027) für Mülheim 1 & 2...")
    try:
        dataset = scraper.fetch_complete_muelheim_dataset(
            years=["2024", "2025", "2026", "2027"]
        )
    except Exception as e:
        if is_local and json_path.exists():
            logger.warning(f"Konnte Live-Daten nicht laden ({e}), verwende bestehende data_muelheim.json...")
            dataset = json.loads(json_path.read_text(encoding="utf-8"))
        else:
            raise

    # Not-Aus Plausibilitätsprüfung (Priorität 4)
    is_plausible, plausibility_error = validate_dataset_plausibility(dataset)
    if not is_plausible:
        print("\n" + "!" * 68)
        print(f"[-] NOT-AUS AKTIVIERT: {plausibility_error}")
        print("[-] Abbruch ohne Schreiben von data_muelheim.json, ergebnisse.html, app.js oder GitHub-Upload.")
        print("!" * 68)
        return

    new_hash = compute_data_hash(dataset)
    data_changed = (last_deploy_hash is None or last_deploy_hash != new_hash)
    html_exists = Path("ergebnisse.html").exists()

    # 1. JSON Export & PWA / HTML Generierung
    # Wird ausgeführt bei Datenänderung, wenn HTML fehlt, oder bei --force / --local
    should_update_files = data_changed or not html_exists or force_deploy or is_local

    if should_update_files:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        print(f"[+] Datensatz gespeichert in: {json_path} (Hash: {new_hash[:10]})")

        generate_pwa_files()
        print("[+] PWA-Assets bereitgestellt (app.js, manifest.json, sw.js, icon-192.png, icon-512.png)")

        current_time_str = datetime.now().strftime("%d.%m.%Y, %H:%M Uhr")
        html_path = "ergebnisse.html"
        scraper.generate_interactive_mobile_html(
            dataset, filepath=html_path, timestamp=current_time_str
        )
        print(f"[+] 'ergebnisse.html' (Tailwind CSS & PWA) generiert mit Zeitstempel: {current_time_str}")

        scraper.generate_interactive_mobile_html(
            dataset, filepath="mobile_view.html", timestamp=current_time_str
        )
    else:
        print(f"[i] Ligadaten unverändert (Hash: {new_hash[:10]}). Bestehende HTML-Dateien werden verwendet.")

    # 2. Konsolenausgabe für das gewählte Jahr und Team
    chosen_year = args.year
    chosen_team = args.team
    team_data = dataset.get(chosen_year, {}).get(chosen_team)

    if team_data:
        print(f"\n====================================================================")
        print(f"AK 50 Herren {chosen_year} • GC Mülheim {chosen_team} ({team_data.get('group_name')})")
        print(f"====================================================================")
        print(f"{'Rang':<6} {'Club':<30} {'Punkte':<8} {'Ø > CR'}")
        print("-" * 55)
        for t in team_data.get("teams", []):
            mark = " <--" if "mülheim" in t["club"].lower() else ""
            print(f"{t['rank']:<6} {t['club']:<30} {t['points']:<8} {t['avg_cr']}{mark}")

        print("\nSpieltage & Spielorte:")
        for day_name, d in team_data.get("matchdays_details", {}).items():
            venue_info = f" ({d['venue']})" if d.get("venue") else ""
            date_info = f" am {d['date']}" if d.get("date") else ""
            tag = " [Ausgefallen / Entfallen]" if d.get("is_canceled") else (" [Nachholspieltag]" if d.get("is_rescheduled") else "")
            print(f"  * {day_name}{date_info}{venue_info}{tag}")
            if d.get("is_canceled"):
                print(f"      (Spieltag fand nicht statt / wurde am 19.09. nachgeholt)")
            elif d.get("team_results"):
                for tr in d["team_results"]:
                    if "mülheim" in tr["team_name"].lower() and tr.get("points"):
                        print(f"      Mülheim Score: {tr['score']} | Punkte: {tr['points']} (Tagestranging: #{tr['rank']})")

    print(f"\n[+] Fertig! 'ergebnisse.html' liegt im aktuellen Verzeichnis.")

    # 3. Deployment auf GitHub Pages
    github_result = None

    if is_local:
        print("\n[+] Lokaler Modus aktiv (--local): GitHub Pages Deployment übersprungen.")
        print("[+] Lokale Web-App aktualisiert: ergebnisse.html & app.js")
    elif data_changed or force_deploy:
        if force_deploy and not data_changed:
            print("\n[+] Option --force aktiv: GitHub Pages Deployment wird trotz unveränderter Daten erzwungen.")
        else:
            print("\n[+] Neue Daten vorhanden: Starte automatisches GitHub Pages Deployment...")

        try:
            github_result = deploy_to_github(html_path="ergebnisse.html")
            if github_result:
                try:
                    hash_file.write_text(new_hash, encoding="utf-8")
                    print(f"[+] Deploy-Hash erfolgreich in .last_deploy_hash gespeichert ({new_hash[:10]}).")
                except Exception as e:
                    logger.warning(f"Konnte .last_deploy_hash nicht speichern: {e}")
        except Exception as e:
            print(f"[-] Unerwarteter Fehler bei deploy_to_github: {e}")
    else:
        print("\n[i] Keine neuen Daten vorhanden (Hash unverändert). Deployment übersprungen.")
        print("[i] Hinweis: Verwende '--force', um das Deployment manuell zu erzwingen.")

    # 4. Ausgabe der Live-URL
    print("\n" + "=" * 68)
    if is_local:
        local_path = Path("ergebnisse.html").resolve()
        print("🌐 LOKALE DATEI:")
        print(f"  * Browser-Pfad: file:///{local_path}")
        print(f"  * Remote-URL:   https://{GITHUB_USER}.github.io/{GITHUB_REPO}/ (nicht aktualisiert)")
    else:
        print("🌐 LIVE-URL:")
        gh_url = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}/"
        if github_result:
            print(f"  * GitHub Pages: {gh_url} (Aktiv aktualisiert)")
        else:
            print(f"  * GitHub Pages: {gh_url}")
    print("=" * 68)


if __name__ == "__main__":
    main()
