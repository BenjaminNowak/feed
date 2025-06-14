import os
import re
import xml.etree.ElementTree as ET  # nosec B405 - Used only for creating elements, not parsing untrusted data
from datetime import datetime, timezone

from defusedxml import ElementTree as DefusedET
from defusedxml.minidom import parseString

from feed_aggregator.storage.mongodb_client import MongoDBClient


def load_feed():
    """Load existing feed.xml or create new one if not exists."""
    # Define feed metadata
    feed_title = "AI and Tech Feed"
    feed_desc = (
        "Curated articles about artificial intelligence, technology, and software "
        "development, filtered by relevance and technical value"
    )
    feed_link = "https://github.com/BenjaminNowak/feed"

    if os.path.exists("feed.xml"):
        tree = DefusedET.parse("feed.xml")
        root = tree.getroot()
        channel = root.find("channel")
        # Update existing channel elements
        title_elem = channel.find("title")
        desc_elem = channel.find("description")
        link_elem = channel.find("link")
        title_elem.text = feed_title
        desc_elem.text = feed_desc
        link_elem.text = feed_link
    else:
        root = ET.Element("rss", version="2.0")
        channel = ET.SubElement(root, "channel")
        ET.SubElement(channel, "title").text = feed_title
        ET.SubElement(channel, "description").text = feed_desc
        ET.SubElement(channel, "link").text = feed_link

    return root, channel


def format_datetime(timestamp_ms):
    """Convert millisecond timestamp to RFC 822 date format."""
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def add_item(channel, article):
    """Add an article to the feed if not already present."""
    # Check if article already exists
    for item in channel.findall("item"):
        if item.find("guid").text == article["id"]:
            return False

    # Create new item
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = article.get("title", "")

    # Get content from either content or summary
    content = article.get("content", {}).get(
        "content", article.get("summary", {}).get("content", "")
    )

    # Clean up HTML
    import re

    # First extract the main content before any social sharing elements
    main_content = content.split("<p><div>", 1)[0].strip()

    # Clean up the main content
    # Remove any remaining HTML tags except <p> and <br>
    main_content = re.sub(r"<(?!/?(?:p|br)(?:\s[^>]*)?>)[^>]+>", "", main_content)

    # Fix escaped quotes and clean up HTML entities
    main_content = main_content.replace("&quot;", '"').replace("&amp;", "&")

    # Clean up extra whitespace and normalize line endings
    main_content = re.sub(r"\s*<br\s*/?\s*>\s*", "\n", main_content)
    main_content = re.sub(r"\s*</p>\s*<p>\s*", "\n\n", main_content)
    main_content = re.sub(r"\s+", " ", main_content).strip()

    # Remove any remaining HTML tags
    main_content = re.sub(r"<[^>]+>", "", main_content)

    content = main_content

    ET.SubElement(item, "description").text = content.strip()

    # Get link from alternate
    link = ""
    if article.get("alternate"):
        for alt in article["alternate"]:
            if alt.get("type") == "text/html":
                link = alt.get("href", "")
                break
    ET.SubElement(item, "link").text = link

    # Add publication date
    published = article.get("published", article.get("crawled", 0))
    ET.SubElement(item, "pubDate").text = format_datetime(published)

    # Use Feedly ID as guid
    ET.SubElement(item, "guid").text = article["id"]

    return True


def main():
    mongo_client = MongoDBClient()
    try:
        # Load or create feed
        root, channel = load_feed()

        # Update lastBuildDate
        build_date = channel.find("lastBuildDate")
        if build_date is None:
            build_date = ET.SubElement(channel, "lastBuildDate")
        build_date.text = format_datetime(
            int(datetime.now(timezone.utc).timestamp() * 1000)
        )

        # Get high-scoring articles that haven't been published
        articles = mongo_client.get_filtered_items(min_score=0.6)
        print(f"Found {len(articles)} high-scoring articles")

        articles_added = 0
        for article in articles:
            if add_item(channel, article):
                # Mark as published in MongoDB
                mongo_client.update_item_status(article["id"], "published")
                articles_added += 1
                print(f"Added article: {article.get('title', '')}")
            else:
                print(f"Skipped duplicate article: {article.get('title', '')}")

        # Clean up all items in the feed
        for item in channel.findall("item"):
            desc_elem = item.find("description")
            if desc_elem is not None and desc_elem.text:
                desc = desc_elem.text
                # First extract the main content before any social sharing elements
                main_content = desc.split("<p><div>", 1)[0].strip()

                # Clean up the main content
                # Remove any remaining HTML tags except <p> and <br>
                main_content = re.sub(
                    r"<(?!/?(?:p|br)(?:\s[^>]*)?>)[^>]+>", "", main_content
                )

                # Fix escaped quotes and clean up HTML entities
                main_content = main_content.replace("&quot;", '"').replace("&amp;", "&")

                # Clean up extra whitespace and normalize line endings
                main_content = re.sub(r"\s*<br\s*/?\s*>\s*", "\n", main_content)
                main_content = re.sub(r"\s*</p>\s*<p>\s*", "\n\n", main_content)
                main_content = re.sub(r"\s+", " ", main_content).strip()

                # Remove any remaining HTML tags
                main_content = re.sub(r"<[^>]+>", "", main_content)

                # Update the description
                item.find("description").text = main_content.strip()

            # Clean up link URLs
            link_elem = item.find("link")
            if link_elem is not None and link_elem.text and "?" in link_elem.text:
                link_elem.text = link_elem.text.split("?")[0]

        # Save the updated feed
        ET.ElementTree(root)
        # Generate clean XML without extra whitespace
        xml_str = ET.tostring(root, encoding="UTF-8")
        pretty_xml = parseString(xml_str).toprettyxml(indent="  ", encoding="UTF-8")
        # Remove empty lines
        clean_xml = "\n".join(
            line for line in pretty_xml.decode().split("\n") if line.strip()
        )

        with open("feed.xml", "w", encoding="UTF-8") as f:
            f.write(clean_xml)
        print(f"\nAdded {articles_added} new articles to feed.xml")

        # Print final stats
        metrics = {
            "total_items": mongo_client.feed_items.count_documents({}),
            "pending_items": mongo_client.feed_items.count_documents(
                {"processing_status": "pending"}
            ),
            "processed_items": mongo_client.feed_items.count_documents(
                {"processing_status": "processed"}
            ),
            "filtered_items": mongo_client.feed_items.count_documents(
                {"processing_status": "filtered_out"}
            ),
            "published_items": mongo_client.feed_items.count_documents(
                {"processing_status": "published"}
            ),
        }

        print("\nMongoDB Status:")
        print(f"Total items: {metrics['total_items']}")
        print(f"Pending items: {metrics['pending_items']}")
        print(f"Processed items: {metrics['processed_items']}")
        print(f"Filtered items: {metrics['filtered_items']}")
        print(f"Published items: {metrics['published_items']}")

    finally:
        mongo_client.close()


if __name__ == "__main__":
    main()
