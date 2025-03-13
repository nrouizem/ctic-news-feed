import os

# A list of RSS feed URLs you'd like to scrape.
RSS_FEEDS = [
    "https://www.fiercebiotech.com/rss.xml",
    "https://www.biopharmadive.com/feeds/news/",
    "https://www.biospace.com/drug-development.rss",
    "https://endpts.com/feed/",
    # Add more relevant feeds...
]

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Keywords to help filter biopharma news (optional)
KEYWORDS = ["biopharma", "FDA", "drug", "clinical trial", "vaccine", "oncology"]
AREAS = ["Ophthalmology", "Immunology", "Oncology", "CNS"]

# Path where we'll write the final RSS feed
OUTPUT_FEED_PATH = "output/custom_feed.xml"

# Basic info for the feed (title, link, description)
FEED_TITLE = ""
FEED_LINK = "https://nrouizem.github.io/test/custom_feed.xml"
BASE_FEED_LINK = "https://nrouizem.github.io/test/"
FEED_DESCRIPTION = "Daily curated & summarized biopharma news."