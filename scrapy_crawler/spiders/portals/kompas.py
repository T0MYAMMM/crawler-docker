import random
import re
import time
import scrapy
from urllib.parse import quote, unquote, urlparse, parse_qs, urljoin

from scrapy_crawler.items import URLDiscoveryItem
from scrapy_crawler.spiders.portals.portal_base import PortalBaseSpider


class KompasSpider(PortalBaseSpider):
    name = "Kompas"
    allowed_domains = ["kompas.com"]
    
    # Configuration for crawling    
    use_date = True 
    time_pattern = '%Y-%m-%d'
    start_urls = ['https://indeks.kompas.com/?site=all&date={new_date}']  
    link_selectors = ['a.article-link::attr(href)']
    existing_next_selectors = ['a.paging__link.paging__link--next::attr(href)']
    use_playwright_request = False
    use_local_proxy = False  
    use_zyte_proxy = False
    auto_rotate_proxy = True

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
            "Referer": f"https://{allowed_domains[0]}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        },
    }

    def parse(self, response):
        """
        Parse page and extract article links using comprehensive selectors.
        - Extract links using CSS selectors
        - Send URLs to Kafka for processing
        - Yield Request objects for pagination
        """

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
                if self._is_valid_link(link) and not self._is_duplicate_link(link):
                    # Convert relative URLs to absolute URLs
                    if link.startswith('/'):
                        link = f"https://{self.allowed_domains[0]}{link}"
                    elif not link.startswith('http'):
                        link = f"https://{self.allowed_domains[0]}/{link}"
                    
                    # Add to crawled data to prevent duplicates
                    self.crawled_data.append(link)
                    
                    # Create proper URLDiscoveryItem
                    item = self.create_url_item(
                        url=link,
                        response=response,
                        is_article=True,
                        content_type='article',
                        priority=75,  # Medium priority for search results
                    )
                    
                    self.logger.info(f"Found article: {link}")
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
                self.logger.info("No more pages available")
            else:
                self.logger.info(f"Reached maximum page limit ({self.page_request} pages)")

    def _extract_article_links(self, response):
        """Extract article links using multiple selector strategies."""
        
        article_links = []
        for selector in self.link_selectors:
            links = response.css(selector).getall()
            article_links.extend(links)
        
        article_links = list(dict.fromkeys(article_links))

        return article_links

    def _find_next_page_link(self, response) -> str:
        """
        Extract next page URL from response.
        
        Args:
            response: Scrapy response object
            
        Returns:
            str: Next page URL or None if no next page
        """

        # Common pagination selectors
        common_next_selectors = [
            'a.next::attr(href)',
            'a[rel="next"]::attr(href)', 
            '.pagination .next::attr(href)',
            '.pager .next::attr(href)',
            'a:contains("Next")::attr(href)',
            'a:contains("Selanjutnya")::attr(href)',
            'a:contains("›")::attr(href)',
            'a:contains("→")::attr(href)',
            '.page-numbers.next::attr(href)',
            'a:contains("Berikutnya")::attr(href)'
        ]
        
        all_next_selectors = self.existing_next_selectors #+ common_next_selectors
        
        for selector in all_next_selectors:
            next_page = response.css(selector).get()
            if next_page:
                # Convert relative URL to absolute URL
                if next_page.startswith('/'):
                    next_page = f"https://{self.allowed_domains[0]}{next_page}"
                elif not next_page.startswith('http'):
                    next_page = f"https://{self.allowed_domains[0]}/{next_page}"
                
                self.logger.info(f"Next page found: {next_page}")
                return next_page
        
        self.logger.info("No next page found")
        return None

    def _is_valid_link(self, link: str) -> bool:
        """
        Validate if the link is worth processing using comprehensive rules.
        
        Args:
            link: URL string to validate
            
        Returns:
            bool: True if link is valid, False otherwise
        """
        if not link:
            return False
            
        # Check minimum length requirement
        if len(link) <= 20:
            return False

        # Apply include/exclude keyword filters
        if not self.include_keyword(link) or not self.exclude_keyword(link):
            return False
        
        # Exclude common non-article links
        exclude_patterns = [
            'javascript:', 'mailto:', '#',
            '/tag/', '/category/', '/author/', '/search/',
            '/login', '/register', '/contact', '/about',
            'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
            '.jpg', '.png', '.gif', '.pdf', '.doc', '.zip',
            '/wp-admin/', '/wp-content/', '/feed/', '/rss/',
            '/sitemap', '/robots.txt', '/privacy', '/terms'
        ]
        
        for pattern in exclude_patterns:
            if pattern in link.lower():
                return False
        
        # Include only links from allowed domains
        if not any(domain in link for domain in self.allowed_domains):
            return False
        
        return True

    def _is_duplicate_link(self, link: str) -> bool:
        """
        Check if link has already been processed.
        
        Args:
            link: URL string to check
            
        Returns:
            bool: True if duplicate, False otherwise
        """
        return link in self.crawled_data

    def exclude_keyword(self, url: str) -> bool:
        """
        Check if URL should be excluded based on keywords.
        
        Args:
            url: URL string to check
            
        Returns:
            bool: True if URL should be included (not excluded), False if excluded
        """
        exclude_keywords = [
            "facebook", "youtube.com", "/authors/", "/author/",
            "twitter.com", "instagram.com", "linkedin.com",
            "/wp-admin/", "/wp-content/", "/feed/", "/rss/",
            "/sitemap", "/robots.txt", "/privacy", "/terms"
        ]
        
        for keyword in exclude_keywords:
            if keyword in url.lower():
                return False
        return True

    def include_keyword(self, url: str) -> bool:
        """
        Check if URL should be included based on keywords.
        
        Args:
            url: URL string to check
            
        Returns:
            bool: True if URL should be included, False otherwise
        """
        # Must contain at least one allowed domain
        for domain in self.allowed_domains:
            if domain in url:
                return True
        
        return False