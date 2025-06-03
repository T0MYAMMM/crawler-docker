import random
import re
import time
import scrapy
from urllib.parse import quote, unquote, urlparse, parse_qs, urljoin

from scrapy_crawler.items import URLDiscoveryItem
from scrapy_crawler.spiders.search.search_base import SearchBaseSpider


class GoogleSearchSpider(SearchBaseSpider):
    name = 'GoogleSearch'
    base_url = "https://www.google.com/search"
    link_selectors = [
        '//div[contains(@class, "Gx5Zad")]/a/@href',
        '//div[contains(@class, "xpd")]/a/@href',
        '//a[contains(@data-ved, "")]/@href',
        '//h3/a/@href',
    ]
    next_page_selectors = [
        '//a[contains(text(), "Next") or contains(text(), ">") or contains(text(), "Berikutnya") or @id="pnnext" or @aria-label="Next page"]/@href',
        '//a[@id="pnnext"]/@href',
        '//span[contains(@class, "SJajHc")]//a/@href',
    ]
    use_playwright_request = False
    use_local_proxy = False  
    use_zyte_proxy = False
    auto_rotate_proxy = True
    
    def __init__(self, phrases='', timestamp='3d', worker_id=0, page='0', page_request=1, *args, **kwargs):
        
        if not phrases:
            phrases = kwargs.pop('phrases', '')
        
        if not phrases:
            raise ValueError("Search phrases must be provided")
        
        # Validate time period format
        if not re.match(r'^\d+[hdwmy]$', timestamp):
            raise ValueError("Invalid time period format. Must be a number followed by 'h', 'd', 'w', 'm', or 'y'.")
        
        # Convert time period to Google's format
        time_mapping = {'h': 'h', 'd': 'd', 'w': 'w', 'm': 'm', 'y': 'y'}
        time_value = timestamp[:-1]
        time_unit = timestamp[-1]
        qdr_value = f"qdr:{time_mapping[time_unit]}"
        
        # Format query parameters
        params = {
            'q': phrases,
            'tbm': 'nws',
            'tbs': f"{qdr_value},sbd:1",
            'bih': '632',
            'biw': '1396',
            'dpr': '1.38',
        }
        
        # Add pagination if needed
        if int(page) > 0:
            params['start'] = str(int(page) * 10)
        
        # Call parent constructor with proper page_request parameter
        super().__init__(
            phrases=phrases, 
            page_request=int(page_request), 
            worker_id=int(worker_id), 
            **kwargs
        )

        # Build the URL
        url = self.base_url + "?" + "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])

        # Set spider-specific attributes
        self.start_urls = [url]
        self.timestamp = timestamp
        
        self.logger.info(f"Starting URL: {url}")
        self.logger.info(f"Configured to crawl up to {self.page_request} pages")

    def parse(self, response):
        """Parse Google search results and extract article URLs."""
        if response.status != 200:
            self.logger.error(f"Failed to retrieve data: {response.status}")
            return
        
        # Add random delay to mimic human behavior
        delay = random.uniform(self.min_delay, self.max_delay)
        self.logger.info(f"Processing page {self.page_number}/{self.page_request} with a delay of {delay:.2f} seconds...")
        time.sleep(delay)

        # Extract article links using multiple selectors
        article_links = self._extract_article_links(response)
        
        if not article_links:
            self.logger.warning(f"No article links found on page {self.page_number}")
        else:
            self.logger.info(f"Found {len(article_links)} potential article links on page {self.page_number}")
        
        # Process each link
        processed_count = 0
        for link in article_links:
            try:
                processed_url = self._process_google_link(link)
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
                self.logger.info("No more pages available from Google")
            else:
                self.logger.info(f"Reached maximum page limit ({self.page_request} pages)")

    def _extract_article_links(self, response):
        """Extract article links using multiple selector strategies."""
        
        article_links = []
        for selector in self.link_selectors:
            links = response.xpath(selector).extract()
            if links:
                article_links.extend(links)
                break
        
        return article_links

    def _process_google_link(self, link):
        """Process Google redirect URLs to extract actual URLs."""
        # Handle Google's redirect URLs
        if link.startswith('/url?') or 'url?' in link:
            parsed_url = urlparse(link)
            actual_url = parse_qs(parsed_url.query).get('q', [None])[0]
            if actual_url:
                link = actual_url
        
        # Skip Google's internal links
        if link.startswith('/search') or 'google.com' in link:
            return None
        
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