"""
Scrapy Settings for ONM Crawler System

This module contains all configuration settings for the Scrapy crawler system.
Organized into logical sections for better maintainability.
"""

import os
import logging
from scrapy import signals


# =============================================================================
# BASIC SCRAPY CONFIGURATION
# =============================================================================

BOT_NAME = "crawler"
SPIDER_MODULES = ["scrapy_crawler.spiders"]
NEWSPIDER_MODULE = "scrapy_crawler.spiders"

# Robot behavior
ROBOTSTXT_OBEY = False
TELNETCONSOLE_ENABLED = False

# Request fingerprinting and encoding
FEED_EXPORT_ENCODING = "utf-8"


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

def configure_logging(debug_mode=False):
    """
    Configure logging based on debug mode setting.
    
    Args:
        debug_mode (bool): If True, enables DEBUG level logging for detailed output
        
    Returns:
        str: The appropriate log level for Scrapy
    """
    
    if debug_mode:
        # Enable DEBUG logging for detailed troubleshooting
        log_level = 'DEBUG'
        
        # Set main loggers to DEBUG
        logging.getLogger('scrapy').setLevel(logging.DEBUG)
        logging.getLogger('kafka_clients').setLevel(logging.DEBUG)
        logging.getLogger('crawlers').setLevel(logging.DEBUG)
        
    else:
        # Production mode: INFO level with selective suppression
        log_level = 'INFO'
        
        # Keep important scrapy logs at INFO but suppress verbose ones
        logging.getLogger('scrapy.core.engine').setLevel(logging.INFO)
        logging.getLogger('scrapy.core.downloader').setLevel(logging.INFO)
        logging.getLogger('scrapy.utils.log').setLevel(logging.INFO)
        logging.getLogger('scrapy.statscollectors').setLevel(logging.INFO)
        
        # Suppress DropItem errors from core scraper (these are normal pipeline behavior)
        logging.getLogger('scrapy.core.scraper').setLevel(logging.WARNING)
        
        # Hide verbose system logs in production
        logging.getLogger('scrapy.middleware').setLevel(logging.WARNING)
        logging.getLogger('scrapy.addons').setLevel(logging.WARNING)
        logging.getLogger('scrapy.extensions.telnet').setLevel(logging.WARNING)
        logging.getLogger('scrapy.extensions.corestats').setLevel(logging.WARNING)
        logging.getLogger('scrapy.extensions.memusage').setLevel(logging.WARNING)
        logging.getLogger('scrapy.extensions.logstats').setLevel(logging.WARNING)
        logging.getLogger('scrapy.extensions.throttle').setLevel(logging.WARNING)
        
        # Suppress verbose third-party libraries
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('kafka').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        
        # Keep our application loggers at INFO
        logging.getLogger('kafka_clients').setLevel(logging.INFO)
        logging.getLogger('crawlers').setLevel(logging.INFO)
    
    return log_level


# Initialize logging configuration
LOG_LEVEL = configure_logging(debug_mode=False)
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_ENABLED = True
LOG_STDOUT = False  # Prevent duplicate console output
LOG_FILE = None     # No file logging by default
LOGSTATS_INTERVAL = 60  # Reduce stats logging frequency

# =============================================================================
# DOWNLOAD CONFIGURATION
# =============================================================================

# Request delays and timeouts
DOWNLOAD_DELAY = 2
RANDOMIZE_DOWNLOAD_DELAY = 0.5
DOWNLOAD_TIMEOUT = 15

# Retry configuration
RETRY_ENABLED = True
RETRY_TIMES = 3

# Concurrent requests
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8

# AutoThrottle settings for polite crawling
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 5
AUTOTHROTTLE_MAX_DELAY = 60
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

# Cookies
COOKIES_ENABLED = True


# =============================================================================
# USER AGENTS
# =============================================================================

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:109.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:115.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:115.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/106.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0',
    'Mozilla/5.0 (Linux; U; Linux i572 ; en-US) AppleWebKit/533.6 (KHTML, like Gecko) Chrome/53.0.2789.311 Safari/535',
    'Mozilla/5.0 (Windows; U; Windows NT 10.5; WOW64; en-US) AppleWebKit/535.15 (KHTML, like Gecko) Chrome/55.0.1368.292 Safari/601',
    'Mozilla/5.0 (Linux x86_64; en-US) AppleWebKit/602.22 (KHTML, like Gecko) Chrome/49.0.3063.181 Safari/603',
    'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_2_3) AppleWebKit/535.12 (KHTML, like Gecko) Chrome/47.0.1246.203 Safari/602',
    'Mozilla/5.0 (Windows; U; Windows NT 6.2; x64) AppleWebKit/533.22 (KHTML, like Gecko) Chrome/48.0.1565.292 Safari/537'
]


# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================

DOWNLOADER_MIDDLEWARES = {
    "scrapy_crawler.middlewares.CrawlersDownloaderMiddleware": 543,
}


# =============================================================================
# PIPELINE CONFIGURATION
# =============================================================================

ITEM_PIPELINES = {
    'scrapy_crawler.pipelines.ItemEnrichmentPipeline': 100,
    'scrapy_crawler.pipelines.DuplicationFilterPipeline': 200,
    'scrapy_crawler.pipelines.MetricsPipeline': 300,
    'scrapy_crawler.pipelines.KafkaURLPipeline': 400,
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def enable_debug_logging():
    """
    Enable debug logging for troubleshooting.
    Call this function to switch to debug mode at runtime.
    """
    global LOG_LEVEL
    LOG_LEVEL = configure_logging(debug_mode=True)
    return LOG_LEVEL


def disable_debug_logging():
    """
    Disable debug logging and return to production mode.
    Call this function to switch back to production logging.
    """
    global LOG_LEVEL
    LOG_LEVEL = configure_logging(debug_mode=False)
    return LOG_LEVEL


# =============================================================================
# DEVELOPMENT/DEBUG HELPERS
# =============================================================================

def get_current_log_level():
    """Get the current configured log level."""
    return LOG_LEVEL


def print_logging_config():
    """Print current logging configuration for debugging."""
    print("=" * 60)
    print("SCRAPY LOGGING CONFIGURATION")
    print("=" * 60)
    print(f"LOG_LEVEL: {LOG_LEVEL}")
    print(f"LOG_FORMAT: {LOG_FORMAT}")
    print(f"LOG_ENABLED: {LOG_ENABLED}")
    print(f"LOG_STDOUT: {LOG_STDOUT}")
    print(f"LOG_FILE: {LOG_FILE}")
    print(f"LOGSTATS_INTERVAL: {LOGSTATS_INTERVAL}")
    print("=" * 60)
    print("KEY LOGGER LEVELS:")
    print(f"scrapy.core.scraper: {logging.getLogger('scrapy.core.scraper').level}")
    print(f"scrapy.middleware: {logging.getLogger('scrapy.middleware').level}")
    print(f"scrapy.addons: {logging.getLogger('scrapy.addons').level}")
    print("=" * 60)


# =============================================================================
# DEPRECATED/UNUSED SETTINGS (kept for reference)
# =============================================================================

# Uncomment and configure as needed:
# REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
# RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 520, 521]
# PROXIES_FILE = os.path.join(os.path.dirname(__file__), 'proxies.txt')

# =============================================================================
# PROXY CONFIGURATION
# =============================================================================

LOCAL_PROXY = 'http://bandung:456xyz@proxycrawler.dashboard.nolimit.id:2570'
ZYTE_PROXY = 'http://0c671085bb1743bf94aca63032c28ceb:@api.zyte.com:8011'