# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from datetime import datetime


class CrawlersItem(scrapy.Item):
    """Enhanced item for crawler data with proper field definitions."""
    
    # Core URL fields
    url = scrapy.Field()                    # URL of the article/page
    source_name = scrapy.Field()            # Name of the source website  
    source_domain = scrapy.Field()          # Domain of the source website
    referer_url = scrapy.Field()            # Source page (index/category page)
    
    # Crawling metadata
    depth = scrapy.Field()                  # Crawling depth (0: homepage, 1: category, 2: article)
    extracted_at = scrapy.Field()           # Extraction timestamp (ISO 8601)
    user_agent = scrapy.Field()             # Used User Agent
    spider_name = scrapy.Field()            # Name of the spider that found this URL
    
    # Classification fields
    is_article = scrapy.Field()             # Boolean: is this URL an article
    content_type = scrapy.Field()           # Type: 'article', 'category', 'homepage', etc.
    priority = scrapy.Field()               # Priority score (0-100)
    
    # Search/phrase context
    search_phrases = scrapy.Field()         # Search phrases used to find this URL
    worker_id = scrapy.Field()              # Worker/process identifier
    
    # Proxy and technical metadata
    proxy_used = scrapy.Field()             # Proxy information used for request
    response_status = scrapy.Field()        # HTTP response status code
    response_time = scrapy.Field()          # Response time in milliseconds
    
    # Additional metadata for analytics
    language = scrapy.Field()               # Detected/specified language
    country = scrapy.Field()                # Country context
    tags = scrapy.Field()                   # Any classification tags
    
    # Article content (for future use)
    title = scrapy.Field()                  # Title of the article
    content = scrapy.Field()                # Content of the article  
    author = scrapy.Field()                 # Author of the article
    published_at = scrapy.Field()           # Published date of the article
    images = scrapy.Field()                 # Images of the article


class URLDiscoveryItem(CrawlersItem):
    """Specialized item for URL discovery phase."""
    pass


class ContentExtractionItem(CrawlersItem):
    """Specialized item for content extraction phase."""
    pass