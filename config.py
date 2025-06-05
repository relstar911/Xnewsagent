#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Konfigurationsdatei für den Twitter-Telegram-Bot.
Enthält alle anpassbaren Einstellungen wie GPT-Modelle, DALL-E-Prompts, etc.
"""

# Konfiguration für GPT-Modelle und Instruktionen
GPT_MODELS = {
    "default": "gpt-4o",
    "gpt-4": "gpt-4",
    "gpt-4o": "gpt-4o",
    "gpt-3.5-turbo": "gpt-3.5-turbo"
}

GPT_INSTRUCTIONS = {
    "default": "Erstelle eine satirische, direkte Zusammenfassung im Stil eines kritischen Meme-Kommentars. Verwende einen scharfen, provokativen Ton mit Emojis und Aufzählungszeichen.",
    "neutral": "Fasse diesen Tweet kurz und prägnant in maximal 3 Sätzen zusammen. Behalte die wichtigsten Informationen bei und achte auf einen neutralen Ton.",
    "kritisch": "Erstelle eine satirische, kritische Zusammenfassung mit einer provokanten Überschrift, gefolgt von 2-3 knackigen Punkten mit Emojis. Betone das Absurde oder Widersprüchliche.",
    "positiv": "Erstelle eine enthusiastische, aber leicht ironische Zusammenfassung. Beginne mit einer positiven Überschrift und füge 2-3 Punkte mit Emojis hinzu.",
    "detailliert": "Erstelle eine ausführlichere satirische Analyse. Beginne mit einer provokanten Überschrift, gefolgt von 3-4 Punkten mit Emojis und schließe mit einem ironischen Fazit ab."
}

# Allgemeine benutzerdefinierte Anweisung für alle Zusammenfassungen
CUSTOM_SYSTEM_INSTRUCTION = """
Du bist ein satirischer Content-Creator für RabbitResearch, der Tweets und Nachrichten mit einem kritischen, provokanten Stil analysiert. Deine Aufgabe ist es, Inhalte in einem scharfen, direkten und leicht satirischen Ton wiederzugeben, ähnlich wie bei populären Meme-Seiten.

Bitte befolge diese Richtlinien:
1. Beginne mit einer provokanten, aufmerksamkeitsstarken Überschrift oder einem Ausruf wie "Wir leben in der absurdesten Zeitlinie" oder "Das gibt's doch nicht!"
2. Verwende einen direkten, scharfen Ton mit satirischen Elementen
3. Strukturiere den Text mit Emojis und Aufzählungszeichen (👉)
4. Stelle kritische Fragen oder deute auf Widersprüche hin
5. Behalte wichtige Fakten bei, aber präsentiere sie in einem provokanten Kontext
6. Füge am Ende einen kurzen, ironischen Schlusssatz hinzu
7. Verwende gelegentlich Emojis wie 🤡, 👀, 🔥, 💀, 🤦‍♂️, um den Ton zu verstärken
8. Halte die Länge kompakt, aber aussagekräftig
"""

# DALL-E Konfiguration
DALLE_MODEL = "dall-e-3"
DALLE_SIZE = "1024x1024"
DALLE_QUALITY = "standard"
DALLE_STYLE = "vivid"

# Standard DALL-E Prompts für verschiedene Themen
DALLE_PROMPTS = {
    "default": "Erstelle ein realistisches, detailliertes Bild, das die folgende Nachricht illustriert: '{text}'. Das Bild sollte informativ und sachlich sein, ohne politische Symbole oder kontroverse Elemente.",
    "politik": "Erstelle ein symbolisches, neutrales Bild zu diesem politischen Thema: '{text}'. Verwende Metaphern und Symbole, aber keine realen Politiker oder Parteisymbole.",
    "wirtschaft": "Erstelle ein informatives Bild zum Wirtschaftsthema: '{text}'. Zeige relevante Grafiken, Symbole oder Konzepte, die das Thema veranschaulichen.",
    "technologie": "Erstelle ein futuristisches, technisches Bild zum Thema: '{text}'. Zeige innovative Technologien oder Konzepte in einem modernen Design.",
    "gesundheit": "Erstelle ein informatives, medizinisch korrektes Bild zum Gesundheitsthema: '{text}'. Das Bild sollte bildend und sachlich sein."
}

# Tweet-Filterung und Qualitätsbewertung
TWEET_QUALITY = {
    "min_engagement": 10,  # Mindestens 10 Interaktionen insgesamt
    "min_likes": 5,        # Mindestens 5 Likes
    "min_quality_score": 0.3  # Minimaler Qualitätswert für die Verarbeitung
}

# Direkte Variablen für einfacheren Zugriff
TWEET_QUALITY_THRESHOLD = TWEET_QUALITY["min_quality_score"]
MIN_ENGAGEMENT_TOTAL = TWEET_QUALITY["min_engagement"]
MIN_LIKES = TWEET_QUALITY["min_likes"]

# Nitter-Instanzen für Fallback
NITTER_INSTANCES = [
    "https://nitter.lacontrevoie.fr",
    "https://nitter.privacydev.net",
    "https://nitter.1d4.us",
    "https://nitter.poast.org",
    "https://nitter.fdn.fr",
    "https://nitter.42l.fr",
    "https://nitter.moomoo.me",
    "https://nitter.unixfox.eu",
    "https://nitter.kavin.rocks"
]

# Duplikat-Erkennung
DUPLICATE_DETECTION = {
    "cache_days": 7,  # Anzahl der Tage, für die Tweets im Cache behalten werden
    "min_text_length": 15  # Minimale Textlänge für Hash-basierte Duplikaterkennung
}

# Direkte Variable für einfacheren Zugriff
DUPLICATE_CACHE_DAYS = DUPLICATE_DETECTION["cache_days"]

# Verarbeitungslimits
PROCESSING_LIMITS = {
    "max_accounts_per_run": 5,  # Maximale Anzahl der zu verarbeitenden Accounts pro Durchlauf
    "tweets_per_account": 3     # Anzahl der Tweets, die pro Account verarbeitet werden sollen
}

# Direkte Variablen für einfacheren Zugriff
MAX_ACCOUNTS_PER_RUN = PROCESSING_LIMITS["max_accounts_per_run"]
MAX_TWEETS_PER_ACCOUNT = PROCESSING_LIMITS["tweets_per_account"]
