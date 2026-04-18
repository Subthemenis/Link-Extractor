from flask import Flask, render_template, request, send_file
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import requests
import time
import os
import logging
import sys

from playwright.sync_api import sync_playwright

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# -----------------------
# BASIC HELPERS
# -----------------------

def is_valid(url):
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)


def get_posts(blog_url):
    posts = set()

    try:
        res = requests.get(blog_url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
    except:
        return []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "blogspot.com" in href and any(x in href for x in ["/20", "/post"]):
            posts.add(href)

    return list(posts)[:40]


# -----------------------
# PLAYWRIGHT RESOLVER
# -----------------------

def resolve_with_browser(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            page.goto(url, timeout=30000)

            # wait for scripts
            page.wait_for_timeout(4000)

            # try clicking common buttons
            keywords = ["unlock", "continue", "get link", "click here", "download"]

            for word in keywords:
                try:
                    btn = page.locator(f"text={word}").first
                    if btn:
                        btn.click(timeout=3000)
                        page.wait_for_timeout(4000)
                except:
                    pass

            final_url = page.url
            browser.close()

            return final_url

    except:
        return url


# -----------------------
# MAIN CRAWLER
# -----------------------

def crawl():
    visited_posts = set()
    final_links = set()

    blogs = [
        "https://playernation1.blogspot.com",
        "https://afkinfo.blogspot.com",
        "https://ixlquiz.blogspot.com",
        "https://ixlskills.blogspot.com",
        "https://sktechhh.blogspot.com"
    ]

    logger.info("Starting crawl across %d blogs", len(blogs))

    for blog in blogs:
        logger.info("Crawling blog: %s", blog)
        posts = get_posts(blog)
        logger.debug("Found %d posts in %s", len(posts), blog)

        for post in posts:
            if post in visited_posts:
                continue

            visited_posts.add(post)
            logger.info("Processing post: %s", post)

            try:
                res = requests.get(post, timeout=10)
                soup = BeautifulSoup(res.text, "html.parser")
            except:
                logger.debug("Failed to fetch post, skipping: %s", post)
                continue

            links_in_post = 0
            for a in soup.find_all("a", href=True):
                link = urljoin(post, a["href"])

                if not is_valid(link):
                    continue

                if "blogspot.com" in link:
                    continue

                logger.debug("Resolving link with browser: %s", link)
                # 🔥 use browser resolver
                final_url = resolve_with_browser(link)
                final_links.add(final_url)
                links_in_post += 1

            logger.info("Extracted %d link(s) from post: %s", links_in_post, post)
            time.sleep(0.8)

    logger.info("Crawl complete — %d unique link(s) found", len(final_links))

    output_path = "links.txt"

    with open(output_path, "w", encoding="utf-8") as f:
        for link in sorted(final_links):
            f.write(link + "\n")

    return output_path


# -----------------------
# ROUTES
# -----------------------

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file_path = crawl()
        return send_file(file_path, as_attachment=True)

    return render_template("index.html")


# -----------------------
# RUN
# -----------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
