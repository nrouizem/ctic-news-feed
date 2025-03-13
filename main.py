import feedparser
from openai import OpenAI
import time
from feedgen.feed import FeedGenerator
from datetime import datetime
import re
import concurrent.futures
import json
import os
import config

from db import init_db, store_article, get_all_articles

client = OpenAI(
    # for deepseek
    #base_url="https://openrouter.ai/api/v1",
    api_key=config.OPENAI_API_KEY,
)

#model = "deepseek/deepseek-r1:free"
model = "gpt-4o-mini"

def is_relevant_article(title, summary, keywords):
    """
    Check if the article is relevant by seeing if it contains any of our
    desired keywords (case-insensitive).
    """
    text_to_search = (title + " " + summary).lower()
    for kw in keywords:
        if kw.lower() in text_to_search:
            return True
    return False

def is_deal_article(title, summary, area):
    prompt = (
        "Classify whether the following text is related to a business deal, "
        f"acquisition, merger, or similar transaction in {area}. "
        "Answer only with 'yes' or 'no':\n\n"
        f"Text: {title} {summary}\n\n"
    )
    completion = client.chat.completions.create(
        model=model,
        store=False,
        messages=[{"role": "user", "content": prompt}]
    )
    response = completion.choices[0].message.content.strip().lower()
    print(response)
    return "yes" in response

def kw_from_area(area):
    # if file doesn't exist, create it, giving it an empty dict
    if not os.path.exists("keywords.json"):
        with open("keywords.json", 'w') as f:
            json.dump({}, f)
            
    with open("keywords.json", 'r') as f:
        kwdict = json.load(f)
    if area in kwdict.keys():
        return kwdict[area]
    
    try:
        prompt = (
            f"Please provide a list of 20 single-word keywords related to the therapeutic area of {area}. "
            "I will be parsing the output programmatically, so provide only the keywords as a comma-separated list, and nothing else.\n\n"
        )
        completion = client.chat.completions.create(
            model=model,
            store=False,
            messages=[{"role": "user", "content": prompt}]
        )
        # empty string sometimes gets returned
        if completion.choices[0].message.content == '':
            print(f"Retrying keyword creation for {area.lower()}...")
            time.sleep(30)
            return kw_from_area(area)

        keywords = completion.choices[0].message.content + f" {area}"
        keywords = re.split(r'[,\s]+', keywords)
        keywords = [kw.lower() for kw in keywords]
        kwdict[area] = keywords
        with open("keywords.json", "w") as f:
            json.dump(kwdict, f)
        return keywords
    except Exception as e:
        print(f"API error: {e}")
        return None

def summarize_text(text):
    try:
        time.sleep(10)
        prompt = (
            "Please summarize the following article in 2 sentences, "
            "focusing on any mention of business deals, partnerships, mergers, or "
            "acquisitions. If none exist, summarize the article normally. The purpose "
            "is to directly put this summary in a news feed, so the summary should be engaging while being "
            "completely accurate to the article. "
            "Provide only the 2-sentence summary (with a focus on deals if applicable), and nothing else.\n\n"
            f"{text}\n\n"
        )
        completion = client.chat.completions.create(
            model=model,
            store=False,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = completion.choices[0].message.content
        # sometimes there's a weird or empty output
        if "field--name-body" in summary or summary == "":
            print("Bad output, retrying...", summary, text)
            time.sleep(30)
            return summarize_text(text)
        return summary.strip()
    except Exception as e:
        print(f"API error: {e}")
        return None

def parse_entry_date(entry):
    """
    Use feedparser's published_parsed or updated_parsed to get a struct_time,
    then convert it to a Python datetime.
    If there's no valid date, return None or a default.
    """
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime.fromtimestamp(time.mktime(entry.published_parsed))
    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime.fromtimestamp(time.mktime(entry.updated_parsed))
    else:
        return None
    
def strip_html_tags(raw_html):
    return re.sub(r'<.*?>', '', raw_html)

def process_feed(feed_url):
    """
    Process a single feed URL, parse the entries, and store them in the DB.
    """
    print(f"Fetching {feed_url}")
    parsed_feed = feedparser.parse(feed_url)

    for entry in parsed_feed.entries:
        title = entry.get("title", "")
        link = entry.get("link", "")
        feed_summary = entry.get("summary", "")

        # Skip invalid articles
        if not title or not link:
            continue

        feed_summary = strip_html_tags(feed_summary)
        ai_summary = summarize_text(feed_summary)
        if not ai_summary:
            ai_summary = feed_summary[:250] + "..."

        # Parse the published date
        published_dt = parse_entry_date(entry)
        if not published_dt:
            published_dt = datetime.now()
        published_rfc2822 = published_dt.strftime("%a, %d %b %Y %H:%M:%S GMT")

        # Store in DB (feed_url + link are used as a unique key)
        store_article(
            feed_url=feed_url,
            title=title,
            link=link,
            summary=ai_summary,
            published_dt=published_rfc2822,
            db_path="articles.db"
        )

def fetch_and_store_articles():
    """
    For each feed, process it and store in the DB.
    This replaces your previous approach of returning area-based data.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(config.RSS_FEEDS)) as executor:
        futures = [executor.submit(process_feed, feed_url) 
                   for feed_url in config.RSS_FEEDS]
        for future in concurrent.futures.as_completed(futures):
            # Just trigger them; no return needed because we store to DB
            future.result()

def build_rss_feed(curated_articles, area):
    """
    Same as before: given a list of articles relevant to `area`,
    build an RSS feed with feedgen.
    """
    fg = FeedGenerator()
    fg.title(f"{area}" + config.FEED_TITLE)
    fg.link(href=config.BASE_FEED_LINK+f"{area.lower()}_feed.xml", rel="self")
    fg.description(config.FEED_DESCRIPTION)
    fg.language("en")

    for article in curated_articles:
        fe = fg.add_entry()
        fe.title(article["title"])
        fe.link(href=article["link"])
        fe.description(article["summary"])
        fe.pubDate(article["published_str"])  # in RFC format

    return fg

def main():
    init_db("articles.db")

    fetch_and_store_articles()

    all_articles = get_all_articles("articles.db")
    if not all_articles:
        print("No articles found in database.")
        return

    kw_dict = {}
    for area in config.AREAS:
        kw_dict[area] = kw_from_area(area)

    for area in config.AREAS:
        # Filter articles to only those relevant to this area
        relevant_articles = []
        for article in all_articles:
            if is_relevant_article(article["title"], article["summary"], kw_dict[area]):
                relevant_articles.append(article)

        # Sort descending by date
        relevant_articles.sort(key=lambda x: x["published_dt"], reverse=True)

        # Build & write the RSS if there's anything relevant
        if relevant_articles:
            fg = build_rss_feed(relevant_articles, area)
            rss_str = fg.rss_str(pretty=True)
            output_file = f"output/{area.lower()}.xml"
            fg.rss_file(output_file)
            print(f"RSS feed generated: {output_file}")
        else:
            print(f"No articles found for {area}.")

if __name__ == "__main__":
    main()
