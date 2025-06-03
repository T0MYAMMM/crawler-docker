import random
import re
import time
import scrapy
from urllib.parse import quote, unquote, urlparse, parse_qs, urljoin

from utils.kafka_utils import send_url
from scrapy_crawler.items import URLDiscoveryItem
from scrapy_crawler.spiders.search.search_base import SearchBaseSpider


class BingSearchSpider(SearchBaseSpider):
    name = "BingSearch"
    allowed_domains = ["bing.com"]
    link_selectors = [
        'a.title::attr(href)'
    ]
    next_page_selectors = [
        '//a[contains(text(), "Next") or contains(text(), ">") or contains(text(), "Berikutnya") or @id="pnnext" or @aria-label="Next page"]/@href',
        '//a[@id="pnnext"]/@href',
        '//span[contains(@class, "SJajHc")]//a/@href',
    ]
    
    # Base URL for Bing News search
    base_url = "https://www.bing.com/news/search"
    
    use_playwright_request = False
    use_local_proxy = False  
    use_zyte_proxy = False
    auto_rotate_proxy = True

    custom_settings = {
        "DOWNLOAD_DELAY": 1, 
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Referer": "https://bing.com",
        },
    }
    
    def __init__(self, phrases='', lang='EN', country='US', worker_id=0, page_request=1, *args, **kwargs):

        if not phrases:
            phrases = kwargs.pop('phrases', '')
        
        if not phrases:
            raise ValueError("Search phrases must be provided")
         
        # Call parent constructor with proper page_request parameter
        super().__init__(
            phrases=phrases, 
            page_request=int(page_request), 
            worker_id=int(worker_id), 
            **kwargs
        )
        
        # Build search URLs based on parameters
        self.start_urls = self._build_search_urls(phrases, lang, country)
    
        # Set additional attributes after parent initialization
        self.worker_id = worker_id
        self.lang = lang
        self.country = country
        
        # Now we can safely use the logger
        self.logger.info(f"Starting URLs: {len(self.start_urls)} URLs generated")
        self.logger.info(f"Configured to crawl up to {self.page_request} pages")

    def _build_search_urls(self, phrases, lang, country):
        """Build search URLs for different language and country combinations"""
        urls = []
        
        # Base search URL
        base_search_url = f"{self.base_url}?q={quote(phrases)}"
        urls.append(base_search_url)
        
        # Add language-specific URLs
        if lang:
            lang_url = f"{self.base_url}?q={quote(phrases)}&setlang={lang}"
            urls.append(lang_url)
        
        # Add country-specific URLs
        if country:
            country_url = f"{self.base_url}?q={quote(phrases)}&cc={country}"
            urls.append(country_url)
        
        # Add combined language and country URL
        if lang and country:
            combined_url = f"{self.base_url}?q={quote(phrases)}&setlang={lang}&cc={country}"
            urls.append(combined_url)
        
        return urls

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        """Alternative constructor for command line usage with scrapy crawl"""
        spider = cls(*args, **kwargs)
        spider._set_crawler(crawler)
        return spider
    
    def exclude_keyword(self, url):
        """Check if URL should be excluded based on keyword filters"""
        exclude = [
            "facebook", "youtube.com", "/authors/"
        ]
        for keyword in exclude:
            if keyword in url:
                return False
        return True

    def include_keyword(self, url):
        """Check if URL should be included based on keyword filters"""
        include = [
            self.allowed_domains[0],
        ]
        
        for keyword in include:
            if keyword in url:
                return True
        return False

    def parse(self, response):
        """Parse Bing search results and extract article URLs."""
        if response.status != 200:
            self.logger.error(f"Failed to retrieve data: {response.status}")
            return

        # Add random delay to mimic human behavior
        delay = random.uniform(self.min_delay, self.max_delay)
        self.logger.info(f"Processing page {self.page_number}/{self.page_request} with a delay of {delay:.2f} seconds...")
        time.sleep(delay)

        article_links = self._extract_article_links(response)

        if not article_links:
            self.logger.warning(f"No article links found on page {self.page_number}")
        else:
            self.logger.info(f"Found {len(article_links)} potential article links on page {self.page_number}")
        
        # Process each link
        processed_count = 0
        for link in article_links:
            try:
                processed_url = self._process_bing_link(link)
                if processed_url:
                    # Create proper URLDiscoveryItem
                    item = self.create_url_item(
                        url=processed_url,
                        response=response,
                        is_article=True,
                        content_type='article',
                        priority=50,  # Medium priority for search results
                    )
                    
                    self.logger.info(f"Found article: {processed_url}")
                    processed_count += 1
                    yield item
                    
            except Exception as e:
                self.logger.error(f"Error processing link {link}: {e}")
        
        self.logger.info(f"Successfully processed {processed_count} articles from page {self.page_number}")

        # Handle pagination (now properly sync)
        next_page_link = self._find_next_page_link(response)
        if next_page_link and self.page_number < self.page_request:
            next_page_url = urljoin(response.url, next_page_link)
            self.logger.info(f"Found next page link, proceeding to page {self.page_number + 1}/{self.page_request}")
            # For sync parse method, we need to yield Scrapy Request objects directly
            yield self._create_scrapy_request(next_page_url)
        else:
            if not next_page_link:
                self.logger.info("No more pages available from Bing")
            else:
                self.logger.info(f"Reached maximum page limit ({self.page_request} pages)")

    def _extract_article_links(self, response):
        """Extract article links using multiple selector strategies"""
        article_links = []
        for selector in self.link_selectors:
            links = response.css(selector).extract()
            if links:
                article_links.extend(links)
                break
        
        return article_links

    def _process_bing_link(self, link):
        # Ensure it's a complete URL
        if not link.startswith('http'):
            return None
        
        # Decode URL if it's URL-encoded
        decoded_link = unquote(link)
        
        # Basic URL validation
        if len(decoded_link) < 30:
            return None
        
        return decoded_link

    def _find_next_page_link(self, response):
        """Find the next page link."""
        for selector in self.next_page_selectors:
            next_page_link = response.xpath(selector).extract_first()
            if next_page_link:
                return next_page_link
        
        return None