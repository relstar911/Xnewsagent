# Twitter → Telegram KI-Bot 

Dieses Projekt ist ein Telegram-Bot, der Tweets von vorgegebenen Twitter/X-Accounts mit KI zusammenfasst und als satirische, provokante Beiträge unter dem RabbitResearch-Branding in einen Telegram-Kanal postet. Der Bot extrahiert auch Bilder aus Tweets, erkennt externe URLs als Quellen und kann zusätzlich mit DALL-E generierte Bilder hinzufügen.

**Aktualisiert:** 05.06.2025 - Verbesserte Medienpriorisierung, Tonalitäts-Waage und Python 3.12 Kompatibilität.

## Features

- **Hybrid Twitter Scraping**:
  - Primär via `twscrape` mit Authentifizierung
  - Fallback zu Nitter-Instanzen, wenn twscrape fehlschlägt

- **Erweiterte KI-Zusammenfassung**:
  - Unterstützung für verschiedene GPT-Modelle (GPT-4o, GPT-3.5-turbo)
  - Verschiedene Zusammenfassungsstile (neutral, kritisch, positiv, detailliert)
  - Satirischer, provokanter Stil mit Emojis und Aufzählungszeichen
  - Automatische Extraktion externer URLs als nummerierte Quellen
  - Standardisierte Fußzeile mit Social-Media-Links
  - **NEU:** Tonalitäts-Waage zur automatischen Auswahl des Kommentarstils basierend auf Tweet-Inhalt und Engagement-Metriken

- **Medienunterstützung**:
  - Extraktion von Bildern aus Tweets
  - Optionale Bildgenerierung mit DALL-E
  - Unterstützung für mehrere Bilder pro Nachricht
  - **NEU:** Intelligente Medienpriorisierung (Tweet-Medien werden bevorzugt, DALL-E als Fallback)

- **Robuste Fehlerbehandlung**:
  - Automatischer Fallback zwischen Scraping-Methoden
  - Retry-Logik mit exponentiellen Wartezeiten
  - Ausführliche Logging-Ausgaben

- **Duplikationserkennung**:
  - Vermeidung von doppelten Tweets durch Hash-basierte Erkennung
  - Persistenter Cache für verarbeitete Tweets
  - **NEU:** Verbesserte Cache-Verwaltung mit automatischer Bereinigung alter Einträge

## Setup

1. Erstelle und aktiviere ein Python-Umfeld (Python 3.12+ empfohlen):
   ```bash
   python -m venv venv311
   # Windows
   .\venv311\Scripts\activate
   # Linux/Mac
   source venv311/bin/activate
   ```

2. Installiere die Abhängigkeiten:
   ```bash
   pip install -r requirements.txt
   ```

3. Lege eine `.env` Datei mit folgenden Einträgen an:
   ```
   # Erforderlich
   TELEGRAM_BOT_TOKEN=dein_telegram_token
   OPENAI_API_KEY=dein_openai_key
   TELEGRAM_CHANNEL_ID=@dein_kanal
   
   # Für twscrape (Twitter-Login)
   TWITTER_USERNAME=dein_twitter_username
   TWITTER_PASSWORD=dein_twitter_passwort
   TWITTER_EMAIL=deine_email_für_verifizierung
   TWITTER_EMAIL_PASSWORD=dein_email_passwort
   ```

4. Erstelle eine `accounts.txt` Datei mit den zu überwachenden Twitter-Accounts:
   ```
   # Format: username,model,instruction
   elonmusk,default,neutral
   navalny,gpt-4o,kritisch
   BillGates
   ```

5. Starte den Bot:
   ```bash
   python main.py
   ```

## Konfiguration

### Twitter-Accounts

In der `accounts.txt` können Accounts im folgenden Format angegeben werden:
- `username` - Verwendet Standard-Modell und -Instruktion
- `username,model,instruction` - Mit spezifischem Modell und Instruktion

Verfügbare Modelle:
- `default` (GPT-4o)
- `kurz` (GPT-3.5-turbo)
- `detailliert` (GPT-4o)

Verfügbare Instruktionen:
- `default` (satirisch mit Emojis und Aufzählungspunkten)
- `neutral` (sachlich, politisch neutral)
- `kritisch` (satirisch-kritisch mit provokanter Überschrift)
- `positiv` (enthusiastisch-ironisch mit positiver Überschrift)
- `detailliert` (ausführlichere satirische Analyse)

## Hinweise

- Für die Twitter-Authentifizierung wird ein gültiger Twitter/X-Account benötigt
- Bei Problemen mit twscrape wird automatisch auf Nitter-Instanzen zurückgegriffen
- Die Duplikationserkennung verhindert, dass derselbe Tweet mehrfach gepostet wird
- Alle Nachrichten werden unter dem RabbitResearch-Branding gepostet
- Das Nachrichtenformat enthält automatisch eine standardisierte Fußzeile mit Links zu allen Social-Media-Kanälen
- Externe URLs aus Tweets werden automatisch als nummerierte Quellen extrahiert
- Der Bot verwendet einen satirischen, provokanten Stil mit Emojis und Aufzählungspunkten
- **NEU:** Die Tonalitäts-Waage wählt automatisch den passenden Kommentarstil basierend auf Tweet-Inhalt und Engagement-Metriken
- **NEU:** Verbesserte Benutzernamen-Extraktion mit Fallback auf "RabbitResearch"
- **NEU:** Python 3.12 kompatible asynchrone Verarbeitung für Telegram-Nachrichten

## Konfigurationsdateien

- `config.py`: Zentrale Konfigurationsdatei für alle Bot-Einstellungen
- `.env`: Umgebungsvariablen und API-Schlüssel
- `accounts.txt`: Liste der zu überwachenden Twitter-Accounts
- `processed_tweets.json`: Cache-Datei für bereits verarbeitete Tweets

## Technische Details

### Tonalitäts-Waage

Die Tonalitäts-Waage analysiert den Tweet-Inhalt und die Engagement-Metriken, um automatisch den passenden Kommentarstil zu wählen:

- **Neutral**: Standard-Stil für allgemeine Tweets
- **Kritisch**: Für kontroverse oder politische Themen
- **Positiv**: Für positive Nachrichten oder Erfolgsgeschichten
- **Detailliert**: Für komplexe Themen, die eine ausführlichere Analyse erfordern

### Medienpriorisierung

Der Bot priorisiert Medien in folgender Reihenfolge:
1. Bilder aus dem Original-Tweet (wenn vorhanden)
2. DALL-E generierte Bilder (wenn keine Tweet-Bilder vorhanden und DISABLE_IMAGE_GENERATION=False)

### Asynchrone Verarbeitung

Der Bot verwendet eine optimierte Mischung aus synchroner und asynchroner Verarbeitung:
- Synchrone Tweet-Verarbeitung für Einfachheit und Stabilität
- Asynchrone Telegram-Nachrichtenübermittlung mit korrekter Event-Loop-Verwaltung für Python 3.12 Kompatibilität

### Fehlerbehandlung

- Ausführliche Debug-Ausgaben für Tweet-IDs, Text-Länge und extrahierte Benutzernamen
- Robuste Exception-Handling mit detaillierten Traceback-Informationen
- Automatische Wiederherstellung nach temporären Fehlern
