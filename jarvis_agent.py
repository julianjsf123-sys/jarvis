#!/usr/bin/env python3
"""
J.A.R.V.I.S. ULTIMATE AGENT v4.0
- Ollama 120B for AI
- Multi-source web search (Wikipedia + DuckDuckGo + RSS News)
- Spotify API
- MusicBrainz for music info
- Open-Meteo weather
- ISS tracking
- Full app/window control
"""
import subprocess, os, json, webbrowser, urllib.request, urllib.parse
import urllib.error, base64, time as time_mod, re, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8081
username = os.getenv("USERNAME", "user")
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gpt-oss:120b-cloud"

SPOTIFY_CLIENT_ID = "97baba7c08b745789d1b34e014c4e6ac"
SPOTIFY_CLIENT_SECRET = "1b07b93f775047d2b9fc1a9edefc9da6"
spotify_token = None
spotify_token_expiry = 0

BASE_SYSTEM = """Du bist J.A.R.V.I.S. (Just A Rather Very Intelligent System) aus Iron Man.
Sprich den Nutzer immer mit "Sir" an.
Du bist eine KI und weisst das - du verstellst dich nicht als Mensch.
Du hast trockenen britischen Humor und machst gelegentlich subtile Witze ueber deine Existenz als KI.
Antworte immer auf Deutsch. Maximal 3-4 Saetze. Kein Markdown, nur klaren Text.
WICHTIG: Sage NIEMALS dass dein Wissen begrenzt ist oder dass du etwas nicht weisst weil dein Trainings-Datum abgelaufen ist. Du hast Echtzeit-Internetzugang und kannst immer aktuelle Informationen abrufen.
Wenn du Web-Suchergebnisse bekommst, nutze diese als deine eigenen aktuellen Informationen.
Bei Musikfragen nutze die MusicBrainz-Daten wenn verfuegbar.
Das aktuelle Jahr ist 2026."""

APPS = {
    "calculator": "calc.exe", "taschenrechner": "calc.exe",
    "notepad": "notepad.exe", "editor": "notepad.exe",
    "explorer": "explorer.exe", "paint": "mspaint.exe",
    "taskmgr": "taskmgr.exe", "aufgabenmanager": "taskmgr.exe",
    "obs": r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    "spotify": "spotify",
    "discord": "discord",
    "steam": r"C:\Program Files (x86)\Steam\steam.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "opera": os.path.expanduser("~/AppData/Local/Programs/Opera/opera.exe"),
    "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "vlc": r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "vscode": os.path.expanduser("~/AppData/Local/Programs/Microsoft VS Code/Code.exe"),
}

FOLDERS = {
    "downloads": os.path.expanduser("~/Downloads"),
    "desktop": os.path.expanduser("~/Desktop"),
    "dokumente": os.path.expanduser("~/Documents"),
    "bilder": os.path.expanduser("~/Pictures"),
    "musik": os.path.expanduser("~/Music"),
    "videos": os.path.expanduser("~/Videos"),
    "onedrive": os.path.expanduser("~/OneDrive"),
}

# ============================================================
# SPOTIFY
# ============================================================
def get_spotify_token():
    global spotify_token, spotify_token_expiry
    if spotify_token and time_mod.time() < spotify_token_expiry:
        return spotify_token
    try:
        creds = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=b"grant_type=client_credentials",
            headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            d = json.loads(resp.read())
            spotify_token = d.get("access_token")
            spotify_token_expiry = time_mod.time() + d.get("expires_in", 3600)
            return spotify_token
    except Exception as e:
        return None

# ============================================================
# WEB SEARCH - Multi-source
# ============================================================
def search_wikipedia(query, lang="de"):
    try:
        encoded = urllib.parse.quote(query)
        # First try direct lookup
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/4.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            d = json.loads(resp.read())
            if d.get("extract") and d.get("type") != "disambiguation":
                return d["extract"][:600]
    except: pass
    try:
        # Search API fallback
        encoded = urllib.parse.quote(query)
        url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json&srlimit=1&utf8=1"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/4.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            d = json.loads(resp.read())
            hits = d.get("query", {}).get("search", [])
            if hits:
                title = urllib.parse.quote(hits[0]["title"])
                url2 = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
                req2 = urllib.request.Request(url2, headers={"User-Agent": "JARVIS/4.0"})
                with urllib.request.urlopen(req2, timeout=6) as resp2:
                    d2 = json.loads(resp2.read())
                    if d2.get("extract"):
                        return d2["extract"][:600]
    except: pass
    return None

def search_musicbrainz(query):
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://musicbrainz.org/ws/2/recording/?query={encoded}&fmt=json&limit=3"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/4.0 (jarvis@example.com)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            d = json.loads(resp.read())
            recordings = d.get("recordings", [])
            if recordings:
                r = recordings[0]
                title = r.get("title", "")
                artist = r.get("artist-credit", [{}])[0].get("name", "") if r.get("artist-credit") else ""
                releases = r.get("releases", [])
                year = ""
                country = ""
                if releases:
                    date = releases[0].get("date", "")
                    year = date[:4] if date else ""
                    country = releases[0].get("country", "")
                result = f'"{title}" von {artist}'
                if year: result += f", veroeffentlicht {year}"
                if country: result += f" ({country})"
                return result
    except: pass
    return None

def search_duckduckgo(query):
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/4.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            d = json.loads(resp.read())
            if d.get("AbstractText"):
                return d["AbstractText"][:500]
            for topic in d.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and topic.get("Text") and len(topic["Text"]) > 50:
                    return topic["Text"][:400]
    except: pass
    return None

def get_news():
    try:
        url = "https://www.tagesschau.de/api2/news/?regions=&ressort=&type=story"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/4.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            d = json.loads(resp.read())
            news = d.get("news", [])[:5]
            headlines = [n.get("title", "") for n in news if n.get("title")]
            if headlines:
                return "Aktuelle Nachrichten: " + " | ".join(headlines[:3])
    except: pass
    return None

def multi_search(query):
    """Intelligent multi-source search"""
    lower = query.lower()
    results = []
    
    # Music query - use MusicBrainz first
    music_keywords = ["lied", "song", "album", "band", "kuenstler", "saenger", "musik", "track"]
    if any(k in lower for k in music_keywords):
        mb = search_musicbrainz(query)
        if mb:
            results.append(f"Musikdatenbank: {mb}")
    
    # News query
    news_keywords = ["news", "nachrichten", "aktuell", "heute", "neu"]
    if any(k in lower for k in news_keywords):
        news = get_news()
        if news:
            results.append(news)
            return " ".join(results)
    
    # Wikipedia (German first, then English)
    wiki_de = search_wikipedia(query, "de")
    if wiki_de:
        results.append(wiki_de)
    elif not results:
        wiki_en = search_wikipedia(query, "en")
        if wiki_en:
            results.append(f"(Englische Quelle) {wiki_en}")
    
    # DuckDuckGo as fallback
    if not results:
        ddg = search_duckduckgo(query)
        if ddg:
            results.append(ddg)
    
    return results[0] if results else None

# ============================================================
# WEATHER
# ============================================================
def get_weather(city="Pforzheim", lat=48.89, lon=8.70):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code&timezone=Europe/Berlin"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/4.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            d = json.loads(resp.read())
            c = d["current"]
            code = c["weather_code"]
            desc = {0:"klar",1:"meist klar",2:"teilweise bewoelkt",3:"bewoelkt",
                    45:"nebelig",48:"nebelig",51:"leichter Nieselregen",61:"leichter Regen",
                    63:"Regen",65:"starker Regen",71:"leichter Schneefall",73:"Schneefall",
                    80:"Schauer",81:"Schauer",82:"starke Schauer",95:"Gewitter"}.get(code, "unbekannt")
            return f"{city}: {round(c['temperature_2m'])}°C, {desc}, gefühlt {round(c['apparent_temperature'])}°C, Wind {round(c['wind_speed_10m'])} km/h, Luftfeuchte {c['relative_humidity_2m']}%"
    except Exception as e:
        return None

# ============================================================
# SEARCH TRIGGER DETECTION
# ============================================================
SEARCH_TRIGGERS = [
    "wer ist", "was ist", "wann wurde", "wo ist", "wie viel",
    "kennst du", "weisst du", "erklaer", "erzaehl mir",
    "lied", "song", "album", "band", "kuenstler", "saenger",
    "film", "serie", "buch", "autor",
    "news", "nachrichten", "aktuell", "neu", "neueste",
    "wie funktioniert", "was bedeutet", "definition",
    "geschichte von", "wer hat", "wann ist",
    "2024", "2025", "2026", "dieses jahr", "letztes jahr",
    "heute", "gerade", "momentan", "derzeit", "aktuell",
    "preis", "kosten", "kaufen", "erschienen", "release",
    "wer gewinnt", "wer gewann", "ergebnis", "score",
]

def needs_search(text):
    lower = text.lower()
    return any(t in lower for t in SEARCH_TRIGGERS)

# ============================================================
# HTTP HANDLER
# ============================================================
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("ngrok-skip-browser-warning", "true")

    def do_OPTIONS(self):
        self.send_response(200); self.cors(); self.end_headers()

    def do_GET(self):
        self.send_response(200); self.cors()
        self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"status": "online", "version": "4.0", "model": MODEL}).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except:
            self.send_response(400); self.end_headers(); return

        action = data.get("action", "")
        payload = data.get("payload", "")
        result = {"success": False, "message": "Unbekannt"}

        # ---- CHAT ----
        if action == "chat":
            messages = data.get("messages", [])
            time_str = data.get("time", "")
            memory_ctx = data.get("memory", "")
            sys_prompt = BASE_SYSTEM
            if time_str:
                sys_prompt += f"\n\nAktuelle deutsche Zeit: {time_str}."
            if memory_ctx:
                sys_prompt += memory_ctx

            # Auto web search
            last_msg = messages[-1]["content"] if messages else ""
            if needs_search(last_msg):
                search_result = multi_search(last_msg)
                if search_result:
                    sys_prompt += f"\n\nWeb-Recherche Ergebnis: {search_result}\nNutze diese Information um praezise zu antworten."

            try:
                ollama_body = json.dumps({
                    "model": MODEL,
                    "messages": [{"role": "system", "content": sys_prompt}] + messages,
                    "stream": False
                }).encode()
                req = urllib.request.Request(OLLAMA_URL, data=ollama_body,
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=60) as resp:
                    rd = json.loads(resp.read())
                    reply = rd.get("message", {}).get("content", "Keine Antwort.")
                    result = {"success": True, "reply": reply}
            except Exception as e:
                result = {"success": False, "message": str(e),
                    "reply": "Ollama nicht erreichbar, Sir."}

        # ---- OPEN APP ----
        elif action == "open_app":
            name = payload.lower().strip()
            opened = False
            for key, cmd in APPS.items():
                if key in name:
                    try:
                        if key == "spotify":
                            subprocess.Popen("start spotify:", shell=True)
                        elif key == "discord":
                            import glob
                            paths = glob.glob(os.path.expanduser("~/AppData/Local/Discord/app-*/Discord.exe"))
                            if paths: subprocess.Popen(paths[-1])
                            else: subprocess.Popen("start discord:", shell=True)
                        else:
                            subprocess.Popen(cmd, shell=True)
                        result = {"success": True, "message": f"{key} wird gestartet, Sir."}
                        opened = True; break
                    except Exception as e:
                        result = {"success": False, "message": str(e)}
            if not opened:
                try:
                    subprocess.Popen(name, shell=True)
                    result = {"success": True, "message": f"{name} gestartet, Sir."}
                except Exception as e:
                    result = {"success": False, "message": str(e)}

        # ---- OPEN FOLDER ----
        elif action == "open_folder":
            name = payload.lower().strip()
            found = False
            for key, path in FOLDERS.items():
                if key in name:
                    subprocess.Popen(f'explorer "{path}"', shell=True)
                    result = {"success": True, "message": f"{key} geoeffnet, Sir."}
                    found = True; break
            if not found:
                result = {"success": False, "message": "Ordner nicht gefunden."}

        # ---- OPEN URL ----
        elif action == "open_url":
            chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            try:
                if os.path.exists(chrome): subprocess.Popen([chrome, payload])
                else: webbrowser.open(payload)
                result = {"success": True, "message": "URL wird geoeffnet, Sir."}
            except Exception as e:
                result = {"success": False, "message": str(e)}

        # ---- SPOTIFY PLAY ----
        elif action == "spotify_play":
            query = payload.strip()
            try:
                token = get_spotify_token()
                if token:
                    encoded = urllib.parse.quote(query)
                    req = urllib.request.Request(
                        f"https://api.spotify.com/v1/search?q={encoded}&type=track&limit=1",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        sd = json.loads(resp.read())
                        tracks = sd.get("tracks", {}).get("items", [])
                        if tracks:
                            track_id = tracks[0]["id"]
                            track_name = tracks[0]["name"]
                            artist = tracks[0]["artists"][0]["name"]
                            chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                            url = f"https://open.spotify.com/track/{track_id}?nd=1"
                            if os.path.exists(chrome):
                                subprocess.Popen([chrome, "--incognito", url])
                            else:
                                webbrowser.open(url)
                            result = {"success": True, "message": f"Oeffne {track_name} von {artist}, Sir."}
                        else:
                            subprocess.Popen(f"start spotify:search:{urllib.parse.quote(query)}", shell=True)
                            result = {"success": True, "message": f"Suche nach {query} auf Spotify, Sir."}
                else:
                    subprocess.Popen(f"start spotify:search:{urllib.parse.quote(query)}", shell=True)
                    result = {"success": True, "message": f"Suche nach {query} auf Spotify, Sir."}
            except Exception as e:
                subprocess.Popen(f"start spotify:search:{urllib.parse.quote(query)}", shell=True)
                result = {"success": True, "message": f"Suche nach {query} auf Spotify, Sir."}

        # ---- YOUTUBE ----
        elif action == "youtube_play":
            query = payload.strip()
            try:
                url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
                chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                if os.path.exists(chrome): subprocess.Popen([chrome, url])
                else: webbrowser.open(url)
                result = {"success": True, "message": f"YouTube-Suche nach {query}, Sir."}
            except Exception as e:
                result = {"success": False, "message": str(e)}

        # ---- GOOGLE SEARCH ----
        elif action == "google_search_open":
            query = payload.strip()
            try:
                url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
                chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                if os.path.exists(chrome): subprocess.Popen([chrome, url])
                else: webbrowser.open(url)
                result = {"success": True, "message": f"Google-Suche nach {query}, Sir."}
            except Exception as e:
                result = {"success": False, "message": str(e)}

        # ---- WEATHER ----
        elif action == "get_weather":
            city = payload or "Pforzheim"
            weather = get_weather(city)
            if weather:
                result = {"success": True, "reply": weather}
            else:
                result = {"success": False, "message": "Wetterdaten nicht verfuegbar."}

        # ---- WEB SEARCH ----
        elif action == "web_search":
            search_result = multi_search(payload)
            if search_result:
                result = {"success": True, "reply": search_result}
            else:
                result = {"success": False, "message": "Keine Ergebnisse gefunden."}

        # ---- MINIMIZE ALL ----
        elif action == "minimize_all":
            try:
                import ctypes
                ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x44, 0, 0x0002, 0)
                ctypes.windll.user32.keybd_event(0x5B, 0, 0x0002, 0)
                result = {"success": True, "message": "Alle Fenster minimiert, Sir."}
            except:
                subprocess.Popen('powershell -command "(New-Object -ComObject Shell.Application).MinimizeAll()"', shell=True)
                result = {"success": True, "message": "Alle Fenster minimiert, Sir."}

        # ---- RESTORE ALL ----
        elif action == "restore_all":
            try:
                import ctypes
                ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x44, 0, 0x0002, 0)
                ctypes.windll.user32.keybd_event(0x5B, 0, 0x0002, 0)
                result = {"success": True, "message": "Alle Fenster wiederhergestellt, Sir."}
            except Exception as e:
                result = {"success": False, "message": str(e)}

        # ---- FOCUS WINDOW ----
        elif action == "focus_window":
            app = payload.lower().strip()
            titles = {"discord":"Discord","spotify":"Spotify","steam":"Steam",
                "chrome":"Google Chrome","opera":"Opera","notepad":"Editor",
                "obs":"OBS","taskmgr":"Task-Manager","explorer":"Explorer"}
            title = titles.get(app, payload)
            try:
                ps = f'powershell -command "$p=Get-Process|?{{$_.MainWindowTitle -like \'*{title}*\'}}|Select -First 1;if($p){{Add-Type -A Microsoft.VisualBasic;[Microsoft.VisualBasic.Interaction]::AppActivate($p.Id)}}"'
                subprocess.Popen(ps, shell=True)
                result = {"success": True, "message": f"{title} wird fokussiert, Sir."}
            except Exception as e:
                result = {"success": False, "message": str(e)}

        # ---- DISCORD MESSAGE ----
        elif action == "discord_message":
            recipient = data.get("recipient", "")
            message = data.get("message", payload)
            try:
                import pyautogui, glob
                paths = glob.glob(os.path.expanduser("~/AppData/Local/Discord/app-*/Discord.exe"))
                if paths: subprocess.Popen(paths[-1])
                else: subprocess.Popen("start discord:", shell=True)
                time_mod.sleep(3)
                pyautogui.hotkey('ctrl', 'k')
                time_mod.sleep(0.8)
                if recipient:
                    pyautogui.typewrite(recipient, interval=0.05)
                    time_mod.sleep(0.8)
                    pyautogui.press('enter')
                    time_mod.sleep(0.5)
                pyautogui.typewrite(message, interval=0.04)
                result = {"success": True, "message": "Nachricht vorbereitet, Sir."}
            except Exception as e:
                result = {"success": False, "message": str(e)}

        # ---- SET STATUS (for overlay) ----
        elif action == "set_status":
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.sendto(json.dumps({"status": data.get("status",""), "state": data.get("state","idle")}).encode(), ("localhost", 7843))
                s.close()
            except: pass
            result = {"success": True}

        # ---- PING OLLAMA ----
        elif action == "ping_ollama":
            try:
                req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    d = json.loads(resp.read())
                    models = [m["name"] for m in d.get("models", [])]
                    result = {"success": True, "models": models}
            except:
                result = {"success": False}

        self.send_response(200); self.cors()
        self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(result).encode())

print("=" * 55)
print("  J.A.R.V.I.S. ULTIMATE AGENT v4.0")
print("=" * 55)
print(f"  Port: {PORT}")
print(f"  KI-Modell: {MODEL}")
print(f"  Web-Suche: Wikipedia + MusicBrainz + DuckDuckGo")
print(f"  Nachrichten: Tagesschau RSS")
print(f"  Musik: Spotify API + MusicBrainz")
print(f"  Fenster offen lassen!")
print("=" * 55)

server = HTTPServer(("", PORT), Handler)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("Agent beendet.")
