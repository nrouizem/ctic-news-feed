import sqlite3
import os
from datetime import datetime

def init_db(db_path="articles.db"):
    """
    Create the 'articles' table if it doesn't exist.
    We'll use (feed_url, link) as a UNIQUE constraint so duplicates aren't inserted.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_url TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            summary TEXT,
            published_dt TEXT, -- store as ISO string or RFC2822
            UNIQUE(feed_url, link)
        );
    """)
    conn.commit()
    conn.close()

def store_article(feed_url, title, link, summary, published_dt, db_path="articles.db"):
    """
    Insert an article (if not already present) into the DB.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR IGNORE INTO articles (feed_url, title, link, summary, published_dt)
            VALUES (?, ?, ?, ?, ?)
        """, (feed_url, title, link, summary, published_dt))
        conn.commit()
    except Exception as e:
        print(f"Error inserting article: {e}")
    finally:
        conn.close()

def get_all_articles(db_path="articles.db"):
    """
    Return all articles from the DB as a list of dicts.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        SELECT feed_url, title, link, summary, published_dt
        FROM articles
        ORDER BY published_dt DESC
    """)
    rows = c.fetchall()
    conn.close()
    
    # Convert rows into a list of dicts
    articles = []
    for row in rows:
        (feed_url, title, link, summary, pub_str) = row

        # If you stored the date as RFC2822, parse accordingly;
        # if you stored it as ISO8601, parse with datetime.fromisoformat(pub_str).
        try:
            published_dt = datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            # fallback or parse differently if needed
            published_dt = datetime.now()

        articles.append({
            "feed_url": feed_url,
            "title": title,
            "link": link,
            "summary": summary,
            "published_dt": published_dt,
            "published_str": pub_str
        })
    return articles
