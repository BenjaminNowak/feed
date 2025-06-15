"""Tests for URL fetcher module."""
import pytest
import responses
from bs4 import BeautifulSoup

from feed_aggregator.fetcher.url_fetcher import URLFetcher


@pytest.fixture
def url_fetcher():
    """Create URL fetcher instance."""
    fetcher = URLFetcher()
    yield fetcher
    fetcher.close()


@pytest.fixture
def mock_html():
    """Sample HTML content."""
    return """
    <html>
        <head>
            <title>Test Page</title>
            <meta property="og:title" content="OG Test Title">
            <meta name="description" content="Meta description">
            <meta property="og:description" content="OG description">
        </head>
        <body>
            <article>
                <h1>Main Article</h1>
                <p>This is the main content.</p>
                <p>More content here.</p>
            </article>
            <div class="sidebar">
                <p>Sidebar content</p>
            </div>
            <script>console.log('test');</script>
            <style>.test { color: red; }</style>
        </body>
    </html>
    """


@responses.activate
def test_fetch_url_content_success(url_fetcher, mock_html):
    """Test successful URL content fetching."""
    test_url = "http://example.com/article"
    responses.add(
        responses.GET, test_url, body=mock_html, status=200, content_type="text/html"
    )

    content = url_fetcher.fetch_url_content(test_url)
    assert content is not None
    assert content["title"] == "OG Test Title"  # Should prefer og:title
    assert (
        content["description"] == "Meta description"
    )  # Should prefer meta description
    assert "main content" in content["main_content"].lower()
    assert "script" not in content["raw_text"]
    assert "style" not in content["raw_text"]


@responses.activate
def test_fetch_url_content_failure(url_fetcher):
    """Test URL fetch failure handling."""
    test_url = "http://example.com/404"
    responses.add(responses.GET, test_url, status=404)

    content = url_fetcher.fetch_url_content(test_url)
    assert content is None


def test_extract_title_fallbacks(url_fetcher):
    """Test title extraction fallback behavior."""
    # Test regular title fallback
    html = "<html><head><title>Regular Title</title></head></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert url_fetcher._extract_title(soup) == "Regular Title"

    # Test empty case
    html = "<html><head></head></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert url_fetcher._extract_title(soup) == ""


def test_extract_description_fallbacks(url_fetcher):
    """Test description extraction fallback behavior."""
    # Test og:description fallback
    html = (
        '<html><head><meta property="og:description" content="OG Desc"></head></html>'
    )
    soup = BeautifulSoup(html, "html.parser")
    assert url_fetcher._extract_description(soup) == "OG Desc"

    # Test empty case
    html = "<html><head></head></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert url_fetcher._extract_description(soup) == ""


def test_extract_main_content_fallbacks(url_fetcher):
    """Test main content extraction fallback behavior."""
    # Test content class selector
    html = '<div class="post-content">Main content here</div>'
    soup = BeautifulSoup(html, "html.parser")
    assert "Main content here" in url_fetcher._extract_main_content(soup)

    # Test paragraph fallback
    html = "<div><p>Small text</p><p>Larger amount of text here</p></div>"
    soup = BeautifulSoup(html, "html.parser")
    assert "Larger amount of text" in url_fetcher._extract_main_content(soup)

    # Test empty case
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert url_fetcher._extract_main_content(soup) == ""
