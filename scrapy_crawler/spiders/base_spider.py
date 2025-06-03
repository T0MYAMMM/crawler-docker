"""
Base Spider Module

This module defines the base spider class that all spiders inherit from.
It provides common functionality for URL discovery and processing using proper Scrapy items.
"""

import re
import logging
import scrapy
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse
from scrapy.http import Response
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from scrapy_crawler.items import CrawlersItem, URLDiscoveryItem


class BaseSpider(CrawlSpider):
    """Base spider for crawling media websites following Scrapy best practices."""
    
    name = "BaseSpider"
    
    def __init__(self, config: Dict[str, Any] = None, *args, **kwargs):
        """
        Initialize the base spider with configuration.
        
        Args:
            config: Dictionary containing spider configuration
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        super().__init__(*args, **kwargs)
        
        self.config = config or {}
        
        # Set basic crawler parameters
        if config:
            self.allowed_domains = config.get('spider', {}).get('allowed_domains', [])
            self.start_urls = config.get('spider', {}).get('start_urls', [])
            
            # Compile regex patterns
            follow_patterns = config.get('spider', {}).get('follow_patterns', [])
            exclude_patterns = config.get('spider', {}).get('exclude_patterns', [])
            article_patterns = config.get('spider', {}).get('article_rules', {}).get('patterns', [])
            
            self.follow_patterns = [re.compile(pattern) for pattern in follow_patterns]
            self.exclude_patterns = [re.compile(pattern) for pattern in exclude_patterns]
            self.article_patterns = [re.compile(pattern) for pattern in article_patterns]
            
            # Set up link extractor
            self.link_extractor = LinkExtractor(
                allow=self.follow_patterns,
                deny=self.exclude_patterns,
                allow_domains=self.allowed_domains,
                unique=True
            )
            
            # Priority rules
            self.priority_rules = config.get('priority_rules', {})
        
        # Keep track of processed URLs to avoid duplicates
        self.processed_urls: Set[str] = set()
        
        self.logger.info(
            f"Initialized {self.name} with {len(getattr(self, 'allowed_domains', []))} domains "
            f"and {len(getattr(self, 'start_urls', []))} start URLs"
        )
    
    def parse(self, response: Response):
        """
        Default parse method for crawling pages using proper Scrapy items.
        
        Args:
            response: The HTTP response to parse
            
        Yields:
            URLDiscoveryItem instances and follow-up requests
        """
        self.logger.debug(f"Parsing {response.url}")
        
        # Extract all links from the page if link extractor is available
        if hasattr(self, 'link_extractor'):
            links = self.link_extractor.extract_links(response)
            self.logger.debug(f"Found {len(links)} links on {response.url}")
            
            # Process each link
            for link in links:
                url = self._normalize_url(link.url)
                
                # Skip if already processed
                if url in self.processed_urls:
                    continue
                self.processed_urls.add(url)
                
                # Determine if this URL is an article
                is_article = self._is_article_url(url)
                
                # Calculate priority based on rules
                priority = self._calculate_priority(url)
                
                # Create URLDiscoveryItem using proper Scrapy item
                item = URLDiscoveryItem(
                    url=url,
                    referer_url=response.url,
                    source_domain=urlparse(url).netloc,
                    is_article=is_article,
                    priority=priority,
                    depth=response.meta.get('depth', 0),
                    content_type='article' if is_article else 'category',
                    response_status=response.status,
                )
                
                # Yield the URL item
                yield item
                
                # If not an article, follow the link for more crawling
                if not is_article:
                    yield scrapy.Request(
                        url=url,
                        callback=self.parse,
                        priority=priority,
                        meta={'depth': response.meta.get('depth', 0) + 1}
                    )
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to a standard format."""
        url = url.strip()
        if url.endswith('/') and len(url) > 1:
            url = url[:-1]
        return url
    
    def _is_article_url(self, url: str) -> bool:
        """Check if URL is an article based on patterns."""
        if hasattr(self, 'article_patterns'):
            for pattern in self.article_patterns:
                if pattern.search(url):
                    return True
        return False
    
    def _calculate_priority(self, url: str) -> int:
        """Calculate priority for a URL based on priority rules."""
        if not hasattr(self, 'priority_rules'):
            return 0
        
        priority = 0
        for rule_name, rule_config in self.priority_rules.items():
            if self._url_matches_rule(url, rule_config):
                priority += rule_config.get('priority_boost', 0)
        
        return max(0, min(priority, 100))  # Clamp between 0-100
    
    def _url_matches_rule(self, url: str, rule_config: Dict[str, Any]) -> bool:
        """Check if URL matches a priority rule."""
        patterns = rule_config.get('patterns', [])
        for pattern in patterns:
            if re.search(pattern, url):
                return True
        return False