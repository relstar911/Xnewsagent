
import os
import re
import sys
import time
import json
import random
import asyncio
import hashlib
import datetime
import requests
import httpx
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from twscrape import API, gather
from telegram import Bot, InputFile
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

# Importiere Konfigurationsoptionen
from config import (
    GPT_MODELS, GPT_INSTRUCTIONS, CUSTOM_SYSTEM_INSTRUCTION,
    DALLE_MODEL, DALLE_SIZE, DALLE_QUALITY, DALLE_STYLE, DALLE_PROMPTS,
    TWEET_QUALITY_THRESHOLD, MIN_ENGAGEMENT_TOTAL, MIN_LIKES,
    NITTER_INSTANCES, DUPLICATE_DETECTION,
    TONALITY_SCALE, MAX_ACCOUNTS_PER_RUN, MAX_TWEETS_PER_ACCOUNT,
    DISABLE_IMAGE_GENERATION
)

# ENV laden - mit absolutem Pfad zur .env-Datei
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
print(f"Versuche .env-Datei zu laden von: {env_path}")
if os.path.exists(env_path):
    print(f".env-Datei gefunden: {env_path}")
else:
    print(f".env-Datei nicht gefunden: {env_path}")
    
# Erzwinge das Laden der .env-Datei mit override=True
load_dotenv(dotenv_path=env_path, override=True)

# Umgebungsvariablen laden
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')

# Twitter-Zugangsdaten aus .env laden
TWITTER_USERNAME = os.getenv('TWITTER_USERNAME')
TWITTER_PASSWORD = os.getenv('TWITTER_PASSWORD')
TWITTER_EMAIL = os.getenv('TWITTER_EMAIL')
TWITTER_EMAIL_PASSWORD = os.getenv('TWITTER_EMAIL_PASSWORD')

# Debug-Ausgabe
print(f"Geladene Konfiguration:")
print(f"TELEGRAM_BOT_TOKEN: {'*' * 10 if TELEGRAM_BOT_TOKEN else 'Nicht geladen'}")
print(f"TELEGRAM_CHANNEL_ID: {TELEGRAM_CHANNEL_ID if TELEGRAM_CHANNEL_ID else 'Nicht geladen'}")
print(f"TWITTER_USERNAME: {TWITTER_USERNAME if TWITTER_USERNAME else 'Nicht geladen'}")
print(f"TWITTER_PASSWORD: {'*' * 8 if TWITTER_PASSWORD else 'Nicht geladen'}")
print(f"TWITTER_EMAIL: {TWITTER_EMAIL if TWITTER_EMAIL else 'Nicht geladen'}")
print(f"TWITTER_EMAIL_PASSWORD: {'*' * 8 if TWITTER_EMAIL_PASSWORD else 'Nicht geladen'}")
print(f"OPENAI_API_KEY: {'*' * 10 if OPENAI_API_KEY else 'Nicht geladen'}")

# Fallback für fehlende Werte
if not TWITTER_USERNAME or not TWITTER_PASSWORD or not TWITTER_EMAIL or not TWITTER_EMAIL_PASSWORD:
    print("WARNUNG: Twitter-Zugangsdaten fehlen oder sind unvollständig!")

# OpenAI API-Key wird automatisch aus der Umgebungsvariable geladen

# Telegram-Bot mit angepassten Verbindungseinstellungen initialisieren
request = HTTPXRequest(
    connection_pool_size=8,  # Erhöhe die Pool-Größe (Standard ist 1)
    read_timeout=30,         # Erhöhe das Read-Timeout
    write_timeout=30,        # Erhöhe das Write-Timeout
    connect_timeout=30       # Erhöhe das Connect-Timeout
)
bot = Bot(token=TELEGRAM_BOT_TOKEN, request=request)

## Nitter-Instanzen werden aus der Konfigurationsdatei importiert

# Tweets scrapen via twscrape mit Nitter-Fallback

# Twitter API-Client initialisieren
api = API()

# Funktion zum Initialisieren des API-Clients
async def init_twitter_api():
    try:
        # Prüfen, ob bereits Accounts vorhanden sind
        # In neueren twscrape-Versionen gibt es keine accounts() Methode direkt
        # Wir fügen einfach den Account hinzu und prüfen später
        try:
            # Account hinzufügen
            print("Füge Twitter-Account hinzu...")
            await api.pool.add_account(
                TWITTER_USERNAME,
                TWITTER_PASSWORD,
                TWITTER_EMAIL,
                TWITTER_EMAIL_PASSWORD
            )
            print("Account hinzugefügt!")
        except Exception as add_error:
            # Wenn der Fehler "Account already exists" ist, ignorieren wir ihn
            if "already exists" in str(add_error):
                print("Account existiert bereits.")
            else:
                raise add_error
                
        # Einloggen
        print("Logge in Twitter ein...")
        await api.pool.login_all()
        print("Login erfolgreich!")
    except Exception as e:
        print(f"Fehler beim Initialisieren des Twitter-API-Clients: {e}")

# Asynchrone Funktion zum Abrufen von Tweets via twscrape
async def get_tweets_via_twscrape(username, count=10):
    try:
        # Tweets direkt mit dem Benutzernamen abrufen
        try:
            # Versuche zuerst mit der search-Methode
            # Erhöhe das Limit, da wir später filtern werden
            tweets = await gather(api.search(f"from:{username}", limit=count))
            if tweets:
                print(f"Erfolgreich {len(tweets)} Tweets für {username} via twscrape search abgerufen")
                
                # Tweets filtern und nur Hauptbeiträge mit ausreichendem Engagement zurückgeben
                result = []
                # Mindestanforderungen für Engagement aus der Konfiguration verwenden
                min_engagement = MIN_ENGAGEMENT_TOTAL
                min_likes = MIN_LIKES
                
                for tweet in tweets:
                    # Prüfen, ob es sich um eine Antwort handelt (beginnt mit @)
                    raw_content = getattr(tweet, "rawContent", "")
                    is_reply = raw_content.strip().startswith("@") if raw_content else False
                    
                    # Prüfen, ob es eine Antwort auf einen anderen Tweet ist
                    in_reply_to_status_id = getattr(tweet, "inReplyToStatusId", None)
                    in_reply_to_user_id = getattr(tweet, "inReplyToUserId", None)
                    
                    # Überspringe Antworten auf andere Tweets
                    if is_reply or in_reply_to_status_id or in_reply_to_user_id:
                        continue
                    
                    # Engagement-Metriken extrahieren
                    likes = getattr(tweet, "likeCount", 0) or 0
                    retweets = getattr(tweet, "retweetCount", 0) or 0
                    replies = getattr(tweet, "replyCount", 0) or 0
                    quotes = getattr(tweet, "quoteCount", 0) or 0
                    total_engagement = likes + retweets + replies + quotes
                    
                    # Überspringe Tweets mit zu geringem Engagement
                    if total_engagement < min_engagement or likes < min_likes:
                        continue
                    
                    tweet_data = {
                        "id": tweet.id,
                        "text": raw_content,
                        "date": tweet.date,
                        "images": [],
                        "url": f"https://twitter.com/{username}/status/{tweet.id}",
                        "likes": likes,
                        "retweets": retweets,
                        "replies": replies,
                        "quotes": quotes,
                        "engagement_total": total_engagement
                    }
                    
                    # Bilder extrahieren, wenn vorhanden
                    if hasattr(tweet, "media") and tweet.media:
                        try:
                            # Überprüfen, ob media ein iterierbares Objekt ist
                            media_items = tweet.media if hasattr(tweet.media, "__iter__") else [tweet.media]
                            
                            for media in media_items:
                                if hasattr(media, "url") and media.url:
                                    tweet_data["images"].append(media.url)
                                elif hasattr(media, "previewUrl") and media.previewUrl:
                                    tweet_data["images"].append(media.previewUrl)
                        except Exception as media_error:
                            print(f"Fehler beim Extrahieren der Medien: {media_error}")
                            # Fahre fort, auch wenn die Medien nicht extrahiert werden können
                    
                    result.append(tweet_data)
                return result
        except Exception as inner_e:
            print(f"Fehler beim Abrufen der Tweets mit search: {inner_e}")
            # Hier könnte man alternative API-Methoden versuchen
            
        return []
    except Exception as e:
        print(f"Fehler beim Abrufen von Tweets für {username} via twscrape: {e}")
        return []

# Funktion zum Abrufen von Tweets via Nitter (Fallback)
def get_tweets_via_nitter(username, count=3):
    print(f"Versuche, Tweets für {username} via Nitter zu holen...")
    tried_redirects = set()
    for base_url in NITTER_INSTANCES:
        url = f"{base_url}/{username}"
        try:
            r = httpx.get(url, timeout=10, follow_redirects=False)
            # Folge Redirects (302) automatisch, wenn Ziel noch nicht versucht wurde
            if r.status_code == 302 and 'location' in r.headers:
                redirect_url = r.headers['location']
                if redirect_url not in tried_redirects:
                    print(f"Redirect von {base_url} auf {redirect_url}, folge weiter...")
                    tried_redirects.add(redirect_url)
                    try:
                        r2 = httpx.get(redirect_url, timeout=10)
                        r2.raise_for_status()
                        soup = BeautifulSoup(r2.text, "html.parser")
                        return extract_tweets_from_nitter(soup, username, count, redirect_url)
                    except Exception as e2:
                        print(f"Fehler beim Folgen von Redirect {redirect_url}: {e2}")
                        continue
                continue
            if r.status_code == 429:
                print(f"Rate Limit bei {base_url}, versuche nächste Instanz...")
                continue
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            return extract_tweets_from_nitter(soup, username, count, base_url)
        except Exception as e:
            print(f"Fehler bei {base_url} für {username}: {e}")
            continue
    print(f"Keine funktionierende Nitter-Instanz für {username} gefunden.")
    return []

# Hilfsfunktion zum Extrahieren von Tweets und Bildern aus Nitter HTML
def extract_tweets_from_nitter(soup, username, count=3, base_url=None):
    result = []
    # Finde alle Tweet-Container
    tweet_containers = soup.find_all("div", {"class": "timeline-item"})
    
    # Mehr Container durchsuchen, da wir filtern werden
    max_containers = min(len(tweet_containers), count * 3)
    
    for container in tweet_containers[:max_containers]:
        tweet_data = {"text": "", "images": [], "url": ""}
        
        # Tweet-ID und URL extrahieren
        tweet_link = container.find("a", {"class": "tweet-link"})
        if tweet_link and tweet_link.has_attr("href"):
            tweet_path = tweet_link["href"]
            # Tweet-ID aus dem Pfad extrahieren
            tweet_id = tweet_path.split("/")[-1]
            tweet_data["id"] = tweet_id
            
            # URL erstellen
            if base_url and tweet_path.startswith("/"):
                parsed_url = urlparse(base_url)
                tweet_data["url"] = f"{parsed_url.scheme}://{parsed_url.netloc}{tweet_path}"
            else:
                # Fallback auf Standard-Twitter-URL
                tweet_data["url"] = f"https://twitter.com/{username}/status/{tweet_id}"
        
        # Text extrahieren
        content_div = container.find("div", {"class": "tweet-content"})
        if content_div:
            tweet_text = content_div.get_text(strip=True)
            tweet_data["text"] = tweet_text
            
            # Prüfen, ob es sich um eine Antwort handelt (beginnt mit @)
            if tweet_text.startswith("@"):
                continue  # Überspringe Antworten
        
        # Bilder extrahieren
        images = container.find_all("a", {"class": "still-image"})
        for img in images:
            img_src = img.find("img")
            if img_src and img_src.has_attr("src"):
                # Vollständige URL erstellen
                img_url = img_src["src"]
                if img_url.startswith("/") and base_url:
                    # Relative URL in absolute umwandeln mit dem bekannten base_url
                    parsed_url = urlparse(base_url)
                    img_url = f"{parsed_url.scheme}://{parsed_url.netloc}{img_url}"
                tweet_data["images"].append(img_url)
        
        # Engagement-Metriken extrahieren (falls verfügbar)
        tweet_stats = container.find("div", {"class": "tweet-stats"})
        likes = 0
        retweets = 0
        replies = 0
        
        if tweet_stats:
            # Likes extrahieren
            likes_span = tweet_stats.find("span", {"class": "icon-heart"})
            if likes_span and likes_span.parent and likes_span.parent.get_text():
                likes_text = likes_span.parent.get_text().strip()
                try:
                    likes = int(likes_text.replace(',', ''))
                except ValueError:
                    pass
            
            # Retweets extrahieren
            retweets_span = tweet_stats.find("span", {"class": "icon-retweet"})
            if retweets_span and retweets_span.parent and retweets_span.parent.get_text():
                retweets_text = retweets_span.parent.get_text().strip()
                try:
                    retweets = int(retweets_text.replace(',', ''))
                except ValueError:
                    pass
            
            # Antworten extrahieren
            replies_span = tweet_stats.find("span", {"class": "icon-comment"})
            if replies_span and replies_span.parent and replies_span.parent.get_text():
                replies_text = replies_span.parent.get_text().strip()
                try:
                    replies = int(replies_text.replace(',', ''))
                except ValueError:
                    pass
        
        # Engagement-Metriken zum Tweet-Daten-Dictionary hinzufügen
        tweet_data["likes"] = likes
        tweet_data["retweets"] = retweets
        tweet_data["replies"] = replies
        tweet_data["quotes"] = 0  # Nitter zeigt keine Quote-Tweets an
        tweet_data["engagement_total"] = likes + retweets + replies
        
        # Mindestanforderungen für Engagement aus der Konfiguration verwenden
        min_engagement = MIN_ENGAGEMENT_TOTAL
        min_likes = MIN_LIKES
        
        # Überspringe Tweets mit zu geringem Engagement
        if tweet_data["engagement_total"] < min_engagement or tweet_data["likes"] < min_likes:
            continue
        
        if tweet_data["text"]:
            result.append(tweet_data)
            # Wenn wir genug qualitativ hochwertige Tweets haben, brechen wir ab
            if len(result) >= count:
                break
    
    if result:
        print(f"Erfolgreich {len(result)} Tweets für {username} via Nitter abgerufen")
    
    return result

# Hybrid-Funktion zum Abrufen von Tweets (erst twscrape, dann Nitter als Fallback)
def get_latest_tweets(username, count=3):
    """Holt die neuesten Tweets eines Benutzers."""
    try:
        print(f"Versuche, Tweets für {username} via twscrape zu holen...")
        # Initialisiere API, falls nötig
        asyncio.run(init_twitter_api())
        # Tweets abrufen - Erhöhe die Anzahl wegen Filterung
        fetch_count = max(10, count * 5)  # Mindestens 10 oder 5x die gewünschte Anzahl
        tweets = asyncio.run(get_tweets_via_twscrape(username, fetch_count))
        if tweets:
            return tweets
    except Exception as e:
        print(f"Fehler beim Abrufen von Tweets für {username} via twscrape: {e}")
    
    # Wenn twscrape fehlschlägt, versuche es mit Nitter
    print(f"twscrape fehlgeschlagen für {username}, versuche Nitter als Fallback...")
    return get_tweets_via_nitter(username, count)

# Konfiguration wurde bereits am Anfang des Skripts importiert

# Zusammenfassen mit benutzerdefinierten GPT-Modellen und Instruktionen
def summarize_text(text, model_key="default", instruction_key="default"):
    try:
        # Modell und Instruktion auswählen
        model = GPT_MODELS.get(model_key, GPT_MODELS["default"])
        instruction = GPT_INSTRUCTIONS.get(instruction_key, GPT_INSTRUCTIONS["default"])
        
        # Prompt erstellen mit benutzerdefinierter Systemanweisung
        user_prompt = f"{instruction}\n\n{text}"
        
        print(f"Verwende Modell: {model} mit Instruktion: {instruction_key}")
        
        # API-Aufruf mit Fehlerbehandlung und Retry-Logik
        max_retries = 3
        retry_delay = 2  # Sekunden
        
        for attempt in range(max_retries):
            try:
                client = OpenAI()
                completion = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": CUSTOM_SYSTEM_INSTRUCTION},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                return completion.choices[0].message.content.strip()
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Fehler bei OpenAI-Anfrage (Versuch {attempt+1}/{max_retries}): {e}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponentielles Backoff
                else:
                    print(f"Alle Versuche fehlgeschlagen: {e}")
                    return f"[Zusammenfassung nicht möglich: {str(e)}]"  # Fallback-Nachricht
    except Exception as e:
        print(f"Fehler beim Zusammenfassen: {e}")
        return f"[Zusammenfassung nicht möglich: {str(e)}]"  # Fallback-Nachricht

# Funktion zur Generierung eines Bild-Prompts basierend auf dem Tweet-Text
def generate_image_prompt(tweet_text, summary):
    """
    Generiert einen Prompt für die Bildgenerierung basierend auf dem Tweet-Text und der Zusammenfassung.
    
    Args:
        tweet_text: Der Text des Tweets
        summary: Die generierte Zusammenfassung
        
    Returns:
        str: Ein Prompt für die Bildgenerierung oder None, wenn kein Prompt generiert werden konnte
    """
    try:
        # Kombiniere Tweet-Text und Zusammenfassung für besseren Kontext
        combined_text = f"{tweet_text}\n\n{summary}"
        
        # Verwende OpenAI, um einen Bildprompt zu generieren
        client = OpenAI()
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du bist ein Experte für die Erstellung von DALL-E Prompts. "
                                      "Erstelle einen kurzen, prägnanten Prompt (max. 60 Wörter) für DALL-E, "
                                      "der den Inhalt des Tweets visuell darstellt. "
                                      "Der Prompt sollte satirisch, überspitzt und visuell interessant sein. "
                                      "Verwende keine Hashtags oder @-Erwähnungen. "
                                      "Antworte NUR mit dem Prompt, ohne Einleitung oder Erklärung."},
                {"role": "user", "content": combined_text}
            ],
            max_tokens=100
        )
        
        prompt = completion.choices[0].message.content.strip()
        return prompt
    except Exception as e:
        print(f"Fehler bei der Generierung des Bild-Prompts: {e}")
        return None

# Beispiel: Bild generieren mit DALL-E
def generate_image(prompt, topic_key="default"):
    try:
        # Wähle den passenden DALL-E Prompt basierend auf dem Thema
        dalle_prompt_template = DALLE_PROMPTS.get(topic_key, DALLE_PROMPTS["default"])
        
        # Formatiere den Prompt mit dem Text
        safe_prompt = dalle_prompt_template.format(text=prompt)
        
        # Begrenze die Länge des Prompts
        if len(safe_prompt) > 1000:
            safe_prompt = safe_prompt[:997] + "..."
            
        response = OpenAI().images.generate(
            model=DALLE_MODEL,
            prompt=safe_prompt,
            n=1,
            size=DALLE_SIZE,
            quality=DALLE_QUALITY,
            style=DALLE_STYLE
        )
        return response.data[0].url
    except Exception as e:
        print(f"Fehler bei der Bildgenerierung: {e}")
        return None

# Funktion zur Bestimmung des Kommentarstils basierend auf Tweet-Inhalt
def determine_comment_style(tweet_text, tweet_data=None):
    """
    Bestimmt den passenden Kommentarstil basierend auf dem Tweet-Inhalt und der Tonalitäts-Waage.
    
    Args:
        tweet_text: Der Text des Tweets
        tweet_data: Optional, ein Dictionary mit zusätzlichen Daten zum Tweet (Likes, Retweets, etc.)
        
    Returns:
        str: Der zu verwendende Kommentarstil (default, kritisch, positiv, detailliert, neutral)
    """
    # Standardstil, falls keine Übereinstimmung gefunden wird
    default_style = "default"
    
    # Text für Keyword-Matching vorbereiten (Kleinbuchstaben)
    text_lower = tweet_text.lower()
    
    # Zähler für Kategorie-Matches
    category_matches = {}
    
    # Prüfen, welche Kategorien im Text vorkommen
    for category, data in TONALITY_SCALE["categories"].items():
        matches = 0
        for keyword in data["keywords"]:
            if keyword.lower() in text_lower:
                matches += 1
        
        if matches > 0:
            category_matches[category] = matches
    
    # Wenn keine Kategorie gefunden wurde, Standard-Stil verwenden
    if not category_matches:
        return default_style
    
    # Kategorie mit den meisten Übereinstimmungen finden
    best_category = max(category_matches.items(), key=lambda x: x[1])[0]
    
    # Stil der besten Kategorie zurückgeben
    style = TONALITY_SCALE["categories"][best_category]["style"]
    
    # Wenn Tweet-Daten vorhanden sind, Intensität basierend auf Engagement anpassen
    if tweet_data and "public_metrics" in tweet_data:
        metrics = tweet_data["public_metrics"]
        likes = metrics.get("like_count", 0)
        comments = metrics.get("reply_count", 0)
        
        # Prüfen auf kontroverse Inhalte (viele Kommentare im Verhältnis zu Likes)
        if likes > 0 and comments / likes > TONALITY_SCALE["intensity"]["controversial_threshold"]:
            # Bei kontroversen Themen den kritischen Stil verstärken
            if style == "kritisch":
                style = "sehr_kritisch"
            elif style == "neutral":
                style = "kritisch"
    
    return style

# Funktion zur Prüfung und Extraktion von Medien aus einem Tweet
def extract_tweet_media(tweet_data):
    """
    Extrahiert Medien (Bilder, Videos) aus einem Tweet.
    Unterstützt verschiedene Tweet-Strukturen (twscrape und andere Quellen).
    
    Args:
        tweet_data: Dictionary mit Tweet-Daten
        
    Returns:
        dict: Medien-Informationen oder None, wenn keine Medien vorhanden sind
    """
    if not tweet_data:
        return None
        
    # Struktur 1: twscrape Format
    if "media" in tweet_data and tweet_data["media"]:
        for media in tweet_data["media"]:
            media_type = media.get("type")
            
            # Bild zurückgeben
            if media_type == "photo":
                return {
                    "type": "photo",
                    "url": media.get("url") or media.get("preview_image_url"),
                    "alt_text": media.get("alt_text", "")
                }
            
            # Video-Vorschaubild zurückgeben
            elif media_type in ["video", "animated_gif"]:
                return {
                    "type": "video_thumbnail",
                    "url": media.get("preview_image_url"),
                    "alt_text": "Video-Vorschaubild"
                }
    
    # Struktur 2: Alte API-Struktur mit "images"-Liste
    if "images" in tweet_data and isinstance(tweet_data["images"], list) and tweet_data["images"]:
        # Erstes Bild zurückgeben
        return {
            "type": "photo",
            "url": tweet_data["images"][0],
            "alt_text": ""
        }
    
    # Struktur 3: Prüfen auf eingebettete URLs mit Vorschaubildern
    if "entities" in tweet_data and "urls" in tweet_data["entities"]:
        for url_entity in tweet_data["entities"]["urls"]:
            if "images" in url_entity and url_entity["images"]:
                return {
                    "type": "link_preview",
                    "url": url_entity["images"][0]["url"],
                    "alt_text": url_entity.get("description", "Link-Vorschaubild")
                }
    
    return None

# Funktion zum Senden einer Nachricht an Telegram
async def send_telegram_message(tweet_data, summary, tweet_url, image_url=None, media_data=None):
    """
    Sendet eine formatierte Nachricht mit dem Tweet und der KI-Zusammenfassung an den Telegram-Kanal.
    
    Args:
        tweet_data: Dictionary mit Tweet-Daten
        summary: Die KI-generierte Zusammenfassung
        tweet_url: URL zum Original-Tweet
        image_url: Optional, URL zu einem generierten Bild
        media_data: Optional, Dictionary mit Medien-Daten aus dem Tweet
    """
    try:
        # Extrahiere den Benutzernamen aus dem Tweet mit verschiedenen möglichen Strukturen
        username = "Unbekannt"
        if "user" in tweet_data and isinstance(tweet_data["user"], dict) and "username" in tweet_data["user"]:
            username = tweet_data["user"]["username"]
        elif "username" in tweet_data:
            username = tweet_data["username"]
        
        # Extrahiere externe URLs aus dem Tweet-Text für Quellenangaben
        tweet_text = tweet_data.get("text", "")
        external_urls = extract_urls_from_text(tweet_text)
        
        # Formatiere die Nachricht mit Emojis und Aufzählungspunkten
        message = f"{username}\n\n{summary}\n\n"
        
        # Füge Quellenangaben hinzu
        sources = []
        sources.append(f"Original-Tweet ({tweet_url})")
        sources.append(f"@{username} auf X (https://twitter.com/{username})")
        
        # Füge externe URLs als Quellen hinzu
        for i, url in enumerate(external_urls, start=3):
            sources.append(url)
        
        # Formatiere die Quellenangaben
        if sources:
            message += "\nQuellen:\n"
            for i, source in enumerate(sources, start=1):
                message += f"{i} ({source}) - "
            # Entferne das letzte " - "
            message = message[:-3]
        
        # Füge die Fußzeile mit Social-Media-Links hinzu
        message += "\n\nauf telegram (http://t.me/rabbitresearch) 👉auf substack (https://rabbitresearch.substack.com/) 👉auf youtube (https://www.youtube.com/c/RabbitResearch/videos) 👉auf odyssee (https://odysee.com/@rabbitresearch:3) 👉auf X (https://twitter.com/real___rabbit)"
        
        # Medien-Priorität: 1. Tweet-Medien, 2. DALL-E generiertes Bild
        media_to_send = None
        caption = message
        
        # Prüfe, ob Tweet-Medien vorhanden sind
        if media_data and media_data.get("url"):
            # Verwende Medien aus dem Tweet
            media_to_send = media_data.get("url")
            print(f"Verwende Medien aus dem Tweet: {media_to_send}")
        elif image_url:
            # Verwende DALL-E generiertes Bild als Fallback
            media_to_send = image_url
            print(f"Verwende DALL-E generiertes Bild: {media_to_send}")
        
        # Sende die Nachricht mit Medien, falls vorhanden
        if media_to_send:
            # Prüfe, ob die Caption zu lang ist (Telegram-Limit: 1024 Zeichen)
            if len(caption) > 1024:
                # Kürze die Caption auf 1021 Zeichen und füge "..." hinzu
                caption = caption[:1021] + "..."
                
            # Sende Foto mit Caption
            await bot.send_photo(chat_id=TELEGRAM_CHANNEL_ID, photo=media_to_send, caption=caption, parse_mode="HTML")
        else:
            # Sende nur Text, wenn keine Medien vorhanden sind
            await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message, parse_mode="HTML")
            
        # Kurze Pause, um Telegram-API nicht zu überlasten
        await asyncio.sleep(1)
        
        return True
    except Exception as e:
        print(f"Fehler beim Senden der Telegram-Nachricht: {e}")
        # Bei zu langer Nachricht versuche ohne Medien zu senden
        if "caption is too long" in str(e).lower():
            try:
                # Sende Text und Medien getrennt
                if media_to_send:
                    await bot.send_photo(chat_id=TELEGRAM_CHANNEL_ID, photo=media_to_send)
                await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message, parse_mode="HTML")
                return True
            except Exception as inner_e:
                print(f"Auch alternativer Sendeversuch fehlgeschlagen: {inner_e}")
        return False

# Telegram-Posting mit Unterstützung für mehrere Bilder (asynchron)
async def post_to_telegram(summary, image_urls=None, tweet_images=None):
    try:
        # Wenn wir ein DALL-E-Bild und Tweet-Bilder haben, sende alles als Mediengruppe
        all_images = []
        
        # Tweet-Bilder hinzufügen, wenn vorhanden
        if tweet_images and isinstance(tweet_images, list) and tweet_images:
            all_images.extend(tweet_images)
            
        # DALL-E-Bild hinzufügen, wenn vorhanden
        if image_urls and not isinstance(image_urls, list):
            image_urls = [image_urls]  # Einzelnes Bild in Liste umwandeln
        if image_urls:
            all_images.extend(image_urls)
            
        if all_images:
            # Wenn wir mehrere Bilder haben, sende als Mediengruppe
            if len(all_images) > 1:
                # Erstes Bild mit Caption, Rest ohne
                media = [
                    {"type": "photo", "media": all_images[0], "caption": summary, "parse_mode": ParseMode.HTML}
                ]
                # Weitere Bilder ohne Caption
                for img in all_images[1:]:  
                    media.append({"type": "photo", "media": img})
                    
                await bot.send_media_group(chat_id=TELEGRAM_CHANNEL_ID, media=media)
            else:
                # Nur ein Bild
                await bot.send_photo(chat_id=TELEGRAM_CHANNEL_ID, photo=all_images[0], caption=summary, parse_mode=ParseMode.HTML)
        else:
            # Kein Bild, nur Text
            await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=summary, parse_mode=ParseMode.HTML)
            
        print(f"Erfolgreich an Telegram gesendet: {summary[:30]}...")
    except Exception as e:
        print(f"Fehler beim Senden an Telegram: {e}")
        # Versuche es mit einfacher Textnachricht, wenn Bilder fehlschlagen
        try:
            await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=summary, parse_mode=ParseMode.HTML)
            print("Nachricht ohne Bilder gesendet.")
        except Exception as e2:
            print(f"Auch Textnachricht fehlgeschlagen: {e2}")
        
# Synchrone Wrapper-Funktion für einfachere Integration
# Globaler Event-Loop für Telegram-Anfragen
telegram_loop = None
telegram_bot_instance = None

def get_telegram_bot():
    global telegram_bot_instance
    if telegram_bot_instance is None:
        # Erstelle Bot-Instanz mit HTTP-Verbindungspool
        request = HTTPXRequest(connection_pool_size=8)
        telegram_bot_instance = Bot(token=TELEGRAM_BOT_TOKEN, request=request)
    return telegram_bot_instance

def send_to_telegram(summary, image_url=None, tweet_images=None):
    global telegram_loop
    
    # Event-Loop erstellen, wenn keiner existiert
    if telegram_loop is None or telegram_loop.is_closed():
        telegram_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(telegram_loop)
    
    # Funktion im Loop ausführen
    try:
        return telegram_loop.run_until_complete(post_to_telegram(summary, image_url, tweet_images))
    except Exception as e:
        print(f"Fehler beim Senden an Telegram: {e}")
        # Versuche es mit einfacher Textnachricht, wenn Bilder fehlschlagen
        try:
            return telegram_loop.run_until_complete(get_telegram_bot().send_message(
                chat_id=TELEGRAM_CHANNEL_ID, 
                text=summary, 
                parse_mode=ParseMode.HTML
            ))
        except Exception as e2:
            print(f"Auch Textnachricht fehlgeschlagen: {e2}")
            return None
    
# Funktion zum Markieren eines Tweets als verarbeitet
def mark_tweet_as_processed(tweet_text, tweet_id=None, cache_file="processed_tweets.json"):
    """Markiert einen Tweet als verarbeitet, indem er zum Cache hinzugefügt wird."""
    # Hash des Tweet-Inhalts erstellen
    tweet_hash = hashlib.md5(tweet_text.encode('utf-8')).hexdigest()
    
    # Cache laden oder erstellen
    processed_tweets = {}
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                processed_tweets = json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden des Tweet-Caches: {e}")
    
    # Tweet zum Cache hinzufügen
    processed_tweets[tweet_hash] = {
        "timestamp": time.time(),
        "preview": tweet_text[:50] + "..." if len(tweet_text) > 50 else tweet_text,
        "id": tweet_id  # ID speichern, falls vorhanden
    }
    
    # Cache speichern
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(processed_tweets, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Fehler beim Speichern des Tweet-Caches: {e}")

# Funktion zur Überprüfung von Duplikaten
def is_duplicate_tweet(tweet_text, cache_file="processed_tweets.json", tweet_id=None):
    """Überprüft, ob ein Tweet bereits verarbeitet wurde, basierend auf einem Hash des Inhalts oder der Tweet-ID."""
    # Wenn der Tweet-Text zu kurz ist oder nur eine URL enthält, ist er nicht aussagekräftig genug
    if len(tweet_text) < 10 or tweet_text.startswith('http'):
        if not tweet_id:  # Wenn keine ID verfügbar ist, können wir nicht sicher prüfen
            print(f"Tweet-Text zu kurz oder nur URL, kann nicht sicher auf Duplikate prüfen: {tweet_text}")
            return False
    
    # Hash des Tweet-Inhalts erstellen
    tweet_hash = hashlib.md5(tweet_text.encode('utf-8')).hexdigest()
    
    # Cache laden oder erstellen
    processed_tweets = {}
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                processed_tweets = json.load(f)
                
                # Alte Einträge entfernen (älter als die konfigurierte Anzahl von Tagen)
                current_time = time.time()
                cache_expiry = current_time - (DUPLICATE_DETECTION["cache_days"] * 24 * 60 * 60)
                processed_tweets = {k: v for k, v in processed_tweets.items() 
                                   if v.get("timestamp", 0) > cache_expiry}
    except Exception as e:
        print(f"Fehler beim Laden des Tweet-Caches: {e}")
        # Bei Fehler Cache neu erstellen
        processed_tweets = {}
    
    # Prüfen, ob der Hash oder die ID bereits im Cache ist
    is_duplicate = False
    
    # Prüfung nach Hash
    if tweet_hash in processed_tweets:
        is_duplicate = True
        print(f"Tweet als Duplikat erkannt (Hash-Match): {tweet_text[:30]}...")
    
    # Prüfung nach ID, falls vorhanden
    elif tweet_id:
        # Suche nach der ID in allen gespeicherten Tweet-Daten
        for stored_hash, data in processed_tweets.items():
            if data.get("id") == tweet_id:
                is_duplicate = True
                print(f"Tweet als Duplikat erkannt (ID-Match): {tweet_id}")
                break
    
    if not is_duplicate:
        # Neuen Tweet zum Cache hinzufügen
        processed_tweets[tweet_hash] = {
            "timestamp": time.time(),
            "preview": tweet_text[:50] + "..." if len(tweet_text) > 50 else tweet_text,
            "id": tweet_id  # ID speichern, falls vorhanden
        }
        
        # Cache speichern
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(processed_tweets, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern des Tweet-Caches: {e}")
    
    return is_duplicate

# Funktion zur Bewertung der Tweet-Qualität
def evaluate_tweet_quality(tweet_text, tweet_data=None):
    """
    Bewertet die Qualität eines Tweets basierend auf Inhalt und Engagement-Metriken.
    
    Args:
        tweet_text: Der Text des Tweets
        tweet_data: Optional, ein Dictionary mit zusätzlichen Daten zum Tweet (Likes, Retweets, etc.)
        
    Returns: 
        float: Qualitätswert zwischen 0 und 1
        str: Begründung für die Bewertung
    """
    score = 0.5  # Startwert
    reasons = []
    
    # Länge des Tweets bewerten
    if len(tweet_text) < 30:
        score -= 0.2
        reasons.append("Tweet ist sehr kurz")
    elif len(tweet_text) > 100:
        score += 0.1
        reasons.append("Tweet hat gute Länge")
    
    # Prüfen auf reine URLs oder zu viele Hashtags
    if tweet_text.startswith('http'):
        score -= 0.3
        reasons.append("Tweet enthält nur URL")
    
    hashtag_count = tweet_text.count('#')
    if hashtag_count > 5:
        score -= 0.1
        reasons.append(f"Tweet enthält viele Hashtags ({hashtag_count})")
    
    # Prüfen auf Schlüsselwörter, die auf Qualität hindeuten könnten
    quality_keywords = ['analyse', 'studie', 'forschung', 'erklärt', 'wichtig', 'neu']
    for keyword in quality_keywords:
        if keyword.lower() in tweet_text.lower():
            score += 0.05
            reasons.append(f"Enthält Qualitätsbegriff: {keyword}")
    
    # Prüfen auf Fragen oder Diskussionsanregungen
    if '?' in tweet_text:
        score += 0.05
        reasons.append("Tweet enthält Frage/Diskussionsanregung")
    
    # Engagement-Metriken bewerten, wenn verfügbar
    if tweet_data and isinstance(tweet_data, dict):
        # Likes bewerten
        likes = tweet_data.get("likes", 0)
        if likes >= 100:
            score += 0.2
            reasons.append(f"Hohe Anzahl an Likes: {likes}")
        elif likes >= 20:
            score += 0.1
            reasons.append(f"Gute Anzahl an Likes: {likes}")
        
        # Retweets bewerten
        retweets = tweet_data.get("retweets", 0)
        if retweets >= 50:
            score += 0.2
            reasons.append(f"Hohe Anzahl an Retweets: {retweets}")
        elif retweets >= 10:
            score += 0.1
            reasons.append(f"Gute Anzahl an Retweets: {retweets}")
        
        # Kommentare bewerten
        replies = tweet_data.get("replies", 0)
        if replies >= 20:
            score += 0.15
            reasons.append(f"Hohe Anzahl an Kommentaren: {replies}")
        elif replies >= 5:
            score += 0.05
            reasons.append(f"Gute Anzahl an Kommentaren: {replies}")
        
        # Gesamtes Engagement bewerten
        total_engagement = tweet_data.get("engagement_total", 0)
        if total_engagement >= 200:
            score += 0.1
            reasons.append(f"Sehr hohes Gesamtengagement: {total_engagement}")
    
    # Begrenzung des Scores auf 0-1
    score = max(0, min(1, score))
    
    return score, ", ".join(reasons)

# Funktion zum Extrahieren von URLs aus einem Text
def extract_urls_from_text(text):
    import re
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[\w/\-?=%.#+&;]*'
    return re.findall(url_pattern, text)

# Funktion zum Verarbeiten eines Tweets
def process_tweet(tweet_data, account_config):
    """
    Verarbeitet einen einzelnen Tweet und sendet ihn an Telegram.
    
    Args:
        tweet_data: Dictionary mit Tweet-Daten
        account_config: Konfiguration für den Account
        
    Returns:
        bool: True, wenn der Tweet erfolgreich verarbeitet wurde
    """
    try:
        tweet_id = tweet_data.get("id")
        tweet_text = tweet_data.get("text", "")
        
        print(f"DEBUG: Tweet-ID: {tweet_id}, Tweet-Text-Länge: {len(tweet_text)}")
        
        # Benutzername aus verschiedenen möglichen Strukturen extrahieren
        username = "RabbitResearch"  # Standardwert, wenn kein Benutzername gefunden wird
        
        # Versuche, den Benutzernamen aus verschiedenen möglichen Strukturen zu extrahieren
        if "user" in tweet_data:
            if isinstance(tweet_data["user"], dict):
                if "username" in tweet_data["user"]:
                    username = tweet_data["user"]["username"]
                elif "screen_name" in tweet_data["user"]:
                    username = tweet_data["user"]["screen_name"]
        elif "username" in tweet_data:
            username = tweet_data["username"]
        elif "screen_name" in tweet_data:
            username = tweet_data["screen_name"]
        elif "author" in tweet_data and isinstance(tweet_data["author"], dict):
            if "username" in tweet_data["author"]:
                username = tweet_data["author"]["username"]
            elif "screen_name" in tweet_data["author"]:
                username = tweet_data["author"]["screen_name"]
        
        print(f"DEBUG: Extrahierter Benutzername: {username}")
        
        tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
        
        # Prüfe, ob der Tweet bereits verarbeitet wurde
        if is_duplicate_tweet(tweet_text, tweet_id=tweet_id):
            print(f"Tweet {tweet_id} wurde bereits verarbeitet. Überspringe.")
            return False
            
        # Bewerte die Qualität des Tweets
        quality_score, quality_reason = evaluate_tweet_quality(tweet_text, tweet_data)
        if quality_score < TWEET_QUALITY_THRESHOLD:
            print(f"Tweet {tweet_id} hat eine zu niedrige Qualität ({quality_score}): {quality_reason}")
            return False
            
        # Bestimme den Kommentarstil basierend auf dem Tweet-Inhalt
        comment_style = determine_comment_style(tweet_text, tweet_data)
        print(f"Verwende Kommentarstil: {comment_style} für Tweet {tweet_id}")
        
        # Passe die Instruktion basierend auf dem Stil an
        instruction = account_config.get("instruction", "default")
        if comment_style != "default":
            instruction = comment_style
            
        # Extrahiere Medien aus dem Tweet
        media_data = extract_tweet_media(tweet_data)
        
        # Generiere eine KI-Zusammenfassung
        summary = summarize_text(tweet_text, account_config.get("model", "default"), instruction)
        if not summary:
            print(f"Konnte keine Zusammenfassung für Tweet {tweet_id} generieren.")
            return False
            
        # Generiere nur ein Bild, wenn keine Tweet-Medien vorhanden sind
        image_url = None
        if not media_data and not DISABLE_IMAGE_GENERATION:
            image_prompt = generate_image_prompt(tweet_text, summary)
            if image_prompt:
                image_url = generate_image(image_prompt)
                
        # Sende die Nachricht an Telegram
        # Da send_telegram_message asynchron ist, müssen wir es mit asyncio ausführen
        # Wir erstellen einen neuen Event-Loop für jeden Tweet, um Probleme mit geschlossenen Loops zu vermeiden
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(send_telegram_message(tweet_data, summary, tweet_url, image_url, media_data))
        finally:
            loop.close()
        
        # Markiere den Tweet als verarbeitet
        if success:
            mark_tweet_as_processed(tweet_text, tweet_id)
            
        return success
    except Exception as e:
        import traceback
        print(f"Fehler bei der Verarbeitung des Tweets: {e}")
        print("Detaillierter Fehler:")
        traceback.print_exc()
        return False

# Funktion zum Laden der Account-Konfiguration
def load_account_config(filename="accounts.txt"):
    """Lädt Twitter-Accounts mit optionalen GPT-Einstellungen aus einer Datei.
    Format: username,model_key,instruction_key
    Beispiel: elonmusk,default,neutral
    """
    accounts_config = []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                    
                # Kommaseparierte Werte verarbeiten
                parts = line.split(",")
                if not parts[0]:
                    continue
                    
                config = {
                    "username": parts[0].strip(),
                    "model": "default",
                    "instruction": "default"
                }
                
                # Optionale Konfiguration für GPT-Modell und Instruktion
                if len(parts) >= 2:
                    config["model"] = parts[1].strip()
                if len(parts) >= 3:
                    config["instruction"] = parts[2].strip()
                    
                accounts_config.append(config)
        return accounts_config
    except Exception as e:
        print(f"Fehler beim Laden der Account-Konfiguration: {e}")
        return []

if __name__ == "__main__":
    # Accounts mit Konfiguration laden
    accounts_config = load_account_config()
    
    # Wenn keine Accounts gefunden wurden, Standardaccounts verwenden
    if not accounts_config:
        accounts_config = [
            {"username": "elonmusk", "model": "default", "instruction": "default"},
            {"username": "BillGates", "model": "default", "instruction": "default"}
        ]
    
    # Zufällige Reihenfolge der Accounts
    random.shuffle(accounts_config)
    
    print(f"Verarbeite {len(accounts_config)} Twitter-Accounts in zufälliger Reihenfolge\n")
    
    # Begrenze die Anzahl der zu verarbeitenden Accounts
    accounts_to_process = accounts_config[:MAX_ACCOUNTS_PER_RUN]
    
    # Verarbeite jeden Account
    for i, account_config in enumerate(accounts_to_process, 1):
        username = account_config["username"]
        model_key = account_config.get("model", "default")
        instruction_key = account_config.get("instruction", "default")
        
        print(f"[{i}/{len(accounts_to_process)}] Account: {username} | Modell: {model_key} | Instruktion: {instruction_key}")
        
        try:
            # Hole Tweets für den Account mit der bestehenden Funktion
            tweets = get_latest_tweets(username)
            
            if not tweets:
                print(f"Keine Tweets für {username} gefunden. Überspringe diesen Account.")
                continue
                
            print(f"Gefundene Tweets für {username}: {len(tweets)}")
            
            # Verarbeite die neuesten Tweets (begrenzt durch MAX_TWEETS_PER_ACCOUNT)
            for j, tweet in enumerate(tweets[:MAX_TWEETS_PER_ACCOUNT], 1):
                tweet_text = tweet.get("text", "")
                tweet_id = tweet.get("id")
                
                print(f"\n  Tweet {j}/{min(len(tweets), MAX_TWEETS_PER_ACCOUNT)} verarbeiten:")
                print(f"  Tweet-Text: {tweet_text[:80]}...")
                
                # Bewerte die Qualität des Tweets
                quality_score, quality_reason = evaluate_tweet_quality(tweet_text, tweet)
                
                # Engagement-Metriken anzeigen
                engagement = 0
                if "public_metrics" in tweet:
                    likes = tweet["public_metrics"].get("like_count", 0)
                    retweets = tweet["public_metrics"].get("retweet_count", 0)
                    replies = tweet["public_metrics"].get("reply_count", 0)
                    engagement = likes + retweets + replies
                    print(f"  Qualitätsbewertung: {quality_score:.2f} ({quality_reason}) | Engagement: {engagement} (👍 {likes}, 🔄 {retweets}, 💬 {replies})")
                else:
                    print(f"  Qualitätsbewertung: {quality_score:.2f} ({quality_reason})")
                
                # Wenn die Qualität zu niedrig ist, überspringe diesen Tweet
                if quality_score < TWEET_QUALITY_THRESHOLD:
                    print(f"  Tweet hat eine zu niedrige Qualität ({quality_score:.2f}). Überspringe.")
                    continue
                
                try:
                    # Verwende die neue process_tweet-Funktion
                    print(f"  Verarbeite Tweet mit der neuen Medien-Priorisierung und Tonalitäts-Waage...")
                    
                    # Direkter Aufruf der synchronen process_tweet-Funktion
                    success = process_tweet(tweet, account_config)
                    
                    if success:
                        print("  Tweet erfolgreich verarbeitet und an Telegram gesendet!")
                    else:
                        print("  Fehler bei der Verarbeitung des Tweets.")
                    
                    # Kurze Pause zwischen Tweets
                    time.sleep(2)
                        
                except Exception as tweet_error:
                    print(f"  Fehler bei der Verarbeitung des Tweets: {tweet_error}")
                    print(f"  Überspringe diesen Tweet und fahre mit dem nächsten fort.")
                    continue
                    
        except Exception as account_error:
            print(f"Fehler bei der Verarbeitung des Accounts: {account_error}")
            print(f"Überspringe diesen Account und fahre mit dem nächsten fort.")
            continue
            
    print("\nVerarbeitung aller Accounts abgeschlossen.")
