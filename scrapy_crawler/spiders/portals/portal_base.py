"""
Base Spider for News Portal Crawlers

This module provides the PortalBaseSpider class following modern Scrapy best practices.
Designed for Scrapy 2.13+ with async support and proper pipeline architecture.
"""

import logging
import time
import httpx
import scrapy
from typing import Optional, Dict, Any
from datetime import datetime
from scrapy.spiders import CrawlSpider
from scrapy.http import HtmlResponse
from urllib.parse import urlparse

from scrapy_crawler.items import URLDiscoveryItem
from scrapy_crawler.settings import LOCAL_PROXY, ZYTE_PROXY
from scrapy_crawler.spiders.base_spider import BaseSpider
from config.settings import PLAYWRIGHT_BROWSER_API
from utils.proxy_utils import ProxyType

class PortalBaseSpider(BaseSpider):
    """
    Base spider class for news crawling with modular pipeline support.
    
    Features:
    - Portal-based crawling (e.g. news, blog, etc.)
    - Async request handling (Scrapy 2.13+)
    - Playwright browser API integration
    - Proper Scrapy item usage
    - Pipeline-based processing
    - Clean modular architecture
    """
    
    name = "BasePortal"
    crawl_type = "portals"
    start_urls = []
    
    # Playwright configuration
    use_playwright_request = False
    playwright_delay_after_load = 3000
    playwright_timeout = 30.0

    # Proxy configuration
    auto_rotate_proxy = False
    use_zyte_proxy = False
    use_local_proxy = False
    
    # Date-based crawling
    use_date = False

    def __init__(self, page_request: int = 1, debug: str = 'false', worker_id: int = 0, **kwargs):
        """
        Initialize the PortalBaseSpider for news crawling.
        
        Args:
            page_request: Number of pages to request
            debug: Enable debug mode ('true'/'false')
            worker_id: Worker identifier for multi-processing
            **kwargs: Additional arguments
        """
        super().__init__(**kwargs)
        
        # Core attributes
        self.page_request = int(page_request)
        self.worker_id = int(worker_id)
        self.debug_mode = debug.lower() in ('true', '1', 'yes', 'on')
        
        # Request timing
        self.min_delay = kwargs.pop('min_delay', 1)
        self.max_delay = kwargs.pop('max_delay', 5)
        
        # Crawling state
        self.start_time = time.time()
        self.today = datetime.now()
        self.current_date = self.today
        self.page_number = 1
        self.url_pattern = None
        self.proxy = None
        self.error_messages = []
        self.crawled_data = []  # Track processed links for duplicate checking
        
        # Configure logging
        self._configure_logging()
        
        # Log initialization
        self._log_initialization()

        # Auto-rotating proxy system initialization
        self._init_proxy_rotation()

    def _init_proxy_rotation(self):
        """Initialize auto-rotating proxy system."""
        # Proxy rotation cycle: None -> Local -> Zyte
        self.proxy_rotation_cycle = [ProxyType.NONE, ProxyType.LOCAL, ProxyType.ZYTE]
        self.current_proxy_index = 0
        self.proxy_retry_count = {}  # Track retry count per URL
        self.max_proxy_retries = 3  # Maximum retries per URL
        self.failed_urls_with_all_proxies = set()  # URLs that failed with all proxy types
        
        # IP detection patterns - responses that indicate IP blocking/detection
        self.ip_detection_patterns = [
            'access denied', 'blocked', 'forbidden', 'captcha', 'cloudflare',
            'rate limit', 'too many requests', 'suspicious activity',
            'your ip', 'ip address', 'security check', 'verification required',
            'bot detection', 'automated traffic', 'unusual traffic'
        ]
        
        # Status codes that trigger proxy rotation
        self.proxy_rotation_status_codes = [403, 429, 503, 520, 521, 522, 523, 524]
        
        if self.debug_mode:
            self.logger.debug(f"Proxy rotation initialized: {[p.value for p in self.proxy_rotation_cycle]}")
            self.logger.debug(f"IP detection patterns: {len(self.ip_detection_patterns)} patterns loaded")

    def _configure_logging(self):
        """Configure logging based on debug mode."""
        try:
            # Import the configure_logging function from settings
            from scrapy_crawler.settings import configure_logging
            
            # Configure logging based on debug mode
            log_level = configure_logging(debug_mode=self.debug_mode)
            
            # Update Scrapy's log level setting
            if hasattr(self, 'settings'):
                self.settings.set('LOG_LEVEL', log_level)
            
            # Log the current logging configuration (only once per spider class)
            if not hasattr(self.__class__, '_logging_message_shown'):
                if self.debug_mode:
                    self.logger.info("Debug mode enabled - showing all log levels including DEBUG")
                else:
                    self.logger.info("Debug mode disabled - hiding DEBUG messages (use -a debug=true to enable)")
                self.__class__._logging_message_shown = True
                
        except Exception as e:
            # Fallback logging configuration
            if self.debug_mode:
                logging.getLogger('scrapy').setLevel(logging.DEBUG)
                logging.getLogger('kafka_clients').setLevel(logging.DEBUG)
            else:
                logging.getLogger('scrapy').setLevel(logging.INFO)
                logging.getLogger('kafka_clients').setLevel(logging.INFO)
            
            self.logger.warning(f"Could not configure logging from settings: {e}")

    def _log_initialization(self):
        """Log spider initialization details."""
        log_msg = f"Spider {self.name} initialized"
        if self.debug_mode:
            log_msg += " with debug mode enabled"
            self.logger.debug(f"Parameters: page_request={self.page_request}")
        
        self.logger.info(log_msg)

    async def start(self):
        """
        Generate initial requests for crawling (async method for Scrapy 2.13+).
        
        Yields:
            Initial requests for crawling
        """
        self.logger.info(f"Starting requests for {self.name}...")
        
        if self.debug_mode:
            self.logger.debug(f"Processing {len(self.start_urls)} start URLs")
            self.logger.debug(f"Configuration: use_playwright={self.use_playwright_request}")
            self.logger.debug(f"Auto-rotate proxy: {self.auto_rotate_proxy}")
        
        for start_url in self.start_urls:
            self._reset_page_state()
            formatted_url = self._format_url_with_date(start_url)
            self.url_pattern = start_url
            
            if self.use_playwright_request:
                async for request in self._create_playwright_request(formatted_url):
                    yield request
            else:
                yield self._create_scrapy_request(formatted_url)

    def _get_proxy_for_type(self, proxy_type: ProxyType) -> Optional[str]:
        """Get proxy URL for the specified proxy type."""
        if proxy_type == ProxyType.NONE:
            return None
        elif proxy_type == ProxyType.LOCAL:
            return LOCAL_PROXY
        elif proxy_type == ProxyType.ZYTE:
            return ZYTE_PROXY
        return None

    def _configure_proxy(self) -> Optional[str]:
        """Configure proxy settings based on spider configuration."""
        if self.auto_rotate_proxy:
            # Use current proxy in rotation cycle
            current_proxy_type = self.proxy_rotation_cycle[self.current_proxy_index]
            proxy = self._get_proxy_for_type(current_proxy_type)
            
            if self.debug_mode:
                self.logger.debug(f"Auto-rotate proxy: Using {current_proxy_type.value} proxy")
                if proxy:
                    self.logger.debug(f"Proxy URL: {proxy}")
            
            return proxy
        else:
            # Use legacy proxy configuration
            if self.use_zyte_proxy:
                proxy = ZYTE_PROXY
                if self.debug_mode:
                    self.logger.debug(f"Using Zyte proxy: {proxy}")
                return proxy
            elif self.use_local_proxy:
                proxy = LOCAL_PROXY
                if self.debug_mode:
                    self.logger.debug(f"Using local proxy: {proxy}")
                return proxy
        
        if self.debug_mode:
            self.logger.debug("No proxy configured")
        return None
    
    def _should_rotate_proxy(self, response) -> bool:
        """
        Determine if proxy should be rotated based on response.
        
        Args:
            response: Scrapy response object
            
        Returns:
            bool: True if proxy should be rotated, False otherwise
        """
        if not self.auto_rotate_proxy:
            return False
        
        # Check status code
        if response.status in self.proxy_rotation_status_codes:
            if self.debug_mode:
                self.logger.debug(f"Status code {response.status} triggers proxy rotation")
            return True
        
        # Check response body for IP detection patterns
        response_text = response.text.lower()
        for pattern in self.ip_detection_patterns:
            if pattern in response_text:
                if self.debug_mode:
                    self.logger.debug(f"IP detection pattern '{pattern}' found in response")
                return True
        
        # Check response headers for blocking indicators
        headers = response.headers
        blocking_headers = ['cf-ray', 'x-blocked', 'x-access-denied']
        for header in blocking_headers:
            if header.lower().encode() in headers:
                if self.debug_mode:
                    self.logger.debug(f"Blocking header '{header}' found in response")
                return True
        
        return False

    def _rotate_to_next_proxy(self, url: str) -> bool:
        """
        Rotate to the next proxy in the cycle.
        
        Args:
            url: URL being processed
            
        Returns:
            bool: True if rotation successful, False if all proxies exhausted
        """
        if not self.auto_rotate_proxy:
            return False
        
        # Initialize retry count for this URL if not exists
        if url not in self.proxy_retry_count:
            self.proxy_retry_count[url] = 0
        
        self.proxy_retry_count[url] += 1
        
        # Log current proxy status before rotation
        current_proxy_type = self.proxy_rotation_cycle[self.current_proxy_index]
        self.logger.info(f"Rotating away from {current_proxy_type.value} proxy (attempt {self.proxy_retry_count[url]})")
        
        # Check if we've exhausted all retries for this URL
        if self.proxy_retry_count[url] >= self.max_proxy_retries:
            self.failed_urls_with_all_proxies.add(url)
            self.logger.error(f"All {self.max_proxy_retries} proxy attempts exhausted for URL: {url}")
            self.logger.error(f"  - Tried proxies: {[p.value for p in self.proxy_rotation_cycle]}")
            return False
        
        # Move to next proxy in cycle
        previous_proxy_index = self.current_proxy_index
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_rotation_cycle)
        next_proxy_type = self.proxy_rotation_cycle[self.current_proxy_index]
        
        self.logger.warning(f"Rotating to {next_proxy_type.value} proxy for URL: {url} (attempt {self.proxy_retry_count[url]})")
        self.logger.info(f"  - Previous proxy: {self.proxy_rotation_cycle[previous_proxy_index].value}")
        self.logger.info(f"  - Next proxy: {next_proxy_type.value}")
        self.logger.info(f"  - Rotation progress: {self.proxy_retry_count[url]}/{self.max_proxy_retries}")
        
        if self.debug_mode:
            self.logger.debug(f"Proxy rotation: {self.current_proxy_index}/{len(self.proxy_rotation_cycle)}")
            self.logger.debug(f"Full proxy cycle: {[p.value for p in self.proxy_rotation_cycle]}")
        
        return True

    def _reset_page_state(self):
        """Reset page-specific state variables."""
        self.current_date = self.today
        self.page_number = 1

    def _format_url_with_date(self, url: str) -> str:
        """Format URL with current date if use_date is enabled."""
        if self.use_date and hasattr(self, 'time_pattern'):
            return url.format(new_date=self.current_date.strftime(self.time_pattern))
        return url

    def _create_scrapy_request(self, url: str, is_retry: bool = False) -> scrapy.Request:
        """
        Create a standard Scrapy request with proper metadata.
        
        Args:
            url: URL to request
            is_retry: Whether this is a retry request
            
        Returns:
            Configured Scrapy Request object
        """
        self.proxy = self._configure_proxy()

        log_msg = f'Creating request for {url}'
        if self.proxy:
            current_proxy_type = self.proxy_rotation_cycle[self.current_proxy_index] if self.auto_rotate_proxy else "manual"
            log_msg += f" (Proxy: {current_proxy_type} - {self.proxy})"
        if is_retry:
            log_msg += " [RETRY]"
        log_msg += ''
        
        self.logger.info(log_msg)

        if self.debug_mode:
            self.logger.debug(f"Creating Scrapy request for: {url}")
            if self.proxy:
                self.logger.debug(f"Request meta: {{'proxy': '{self.proxy}'}}")
            else:
                self.logger.debug("Request meta: None")

        # Create request meta
        meta = self._build_request_meta()
        if self.proxy:
            meta['proxy'] = self.proxy
        
        # Add auto-rotate proxy metadata
        if self.auto_rotate_proxy:
            meta['auto_rotate_proxy'] = True
            meta['original_url'] = url
            meta['proxy_attempt'] = self.proxy_retry_count.get(url, 0) + 1
        
        return scrapy.Request(
            url=url,
            callback=self._parse_wrapper,
            errback=self._handle_request_error,
            meta=meta,
            dont_filter=is_retry
        )

    def _build_request_meta(self) -> Dict[str, Any]:
        """Build metadata dictionary for requests."""
        return {
            'worker_id': self.worker_id,
            'spider_name': self.name,
        }

    async def _create_playwright_request(self, url: str):
        """
        Create a playwright browser API request asynchronously.
        
        Args:
            url: URL to request via Playwright
            
        Yields:
            Scrapy Request objects configured for Playwright responses
        """
        try:
            if self.debug_mode:
                self.logger.debug(f"Creating Playwright request for: {url}")
                self.logger.debug(f"Playwright config: delay={self.playwright_delay_after_load}ms, timeout={self.playwright_timeout}s")
                self.logger.debug(f"Auto-rotate proxy: {self.auto_rotate_proxy}")

            request_data = self._build_playwright_params(url)
            
            # Handle proxy configuration for Playwright API
            if self.auto_rotate_proxy:
                # Use proxy rotation feature of Playwright API
                current_proxy_type = self.proxy_rotation_cycle[self.current_proxy_index]
                
                # Map our proxy types to Playwright API proxy types
                if current_proxy_type == ProxyType.LOCAL:
                    request_data["proxy_type"] = "local"
                elif current_proxy_type == ProxyType.ZYTE:
                    request_data["proxy_type"] = "zyte"
                elif current_proxy_type == ProxyType.NONE:
                    request_data["proxy_type"] = None
                
                self.logger.info(f'Creating Playwright request for {url} with {current_proxy_type.value} proxy')
                
                if self.debug_mode:
                    self.logger.debug(f"Playwright proxy config: proxy_type={request_data.get('proxy_type')}")
            else:
                # Use legacy proxy configuration
                if self.use_zyte_proxy:
                    request_data["proxy_type"] = "zyte"
                    self.logger.info(f'Creating Playwright request for {url} with Zyte proxy')
                elif self.use_local_proxy:
                    request_data["proxy_type"] = "local"
                    self.logger.info(f'Creating Playwright request for {url} with Local proxy')
                else:
                    self.logger.info(f'Creating Playwright request for {url}')
        
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    PLAYWRIGHT_BROWSER_API, 
                    params=request_data, 
                    timeout=self.playwright_timeout
                )
                
                if response.status_code == 200:
                    yield self._process_playwright_response(url, response)
                else:
                    error_msg = f"Playwright API request failed with status {response.status_code} for {url}"
                    
                    # Check if API provided error details
                    try:
                        error_data = response.json()
                        api_error = error_data.get('error', 'Unknown error')
                        error_msg += f": {api_error}"
                    except:
                        pass
                    
                    self.logger.error(error_msg)
                    
                    # Try proxy rotation for Playwright API failures if auto_rotate_proxy is enabled
                    if (self.auto_rotate_proxy and 
                        response.status_code in self.proxy_rotation_status_codes and
                        url not in self.failed_urls_with_all_proxies):
                        
                        if self._rotate_to_next_proxy(url):
                            self.logger.info(f"Retrying Playwright request with rotated proxy for: {url}")
                            async for retry_request in self._create_playwright_request(url):
                                yield retry_request
                            return
                    
                    self.error_messages.append(error_msg)
                    
        except Exception as e:
            error_msg = f"Error in Playwright request for {url}: {e}"
            self.logger.error(error_msg)
            if self.debug_mode:
                self.logger.debug(f"Playwright request exception details: {str(e)}", exc_info=True)
            
            # Try proxy rotation for network errors if auto_rotate_proxy is enabled
            if (self.auto_rotate_proxy and url not in self.failed_urls_with_all_proxies):
                if self._rotate_to_next_proxy(url):
                    self.logger.info(f"Retrying Playwright request with rotated proxy due to network error for: {url}")
                    async for retry_request in self._create_playwright_request(url):
                        yield retry_request
                    return
            
            self.error_messages.append(error_msg)

    def _build_playwright_params(self, url: str) -> Dict[str, Any]:
        """Build parameters for Playwright API request."""
        return {
            "url": url,
            "delay_after_load": self.playwright_delay_after_load,
            "timeout": self.playwright_timeout
        }

    def _process_playwright_response(self, url: str, response) -> scrapy.Request:
        """
        Process Playwright API response and create Scrapy request.
        
        Args:
            url: Original URL
            response: httpx response from Playwright API
            
        Returns:
            Scrapy Request configured with Playwright response data
        """
        response_data = response.json()
        html_content = response_data.get('html', '')
        
        # Check if Playwright API returned proxy information
        proxy_used = response_data.get('proxy_used', 'none')
        attempt_number = response_data.get('attempt_number', 1)
        total_attempts = response_data.get('total_attempts', 1)
        
        if self.debug_mode:
            self.logger.debug(f"Playwright API response received, HTML length: {len(html_content)}")
            self.logger.debug(f"Proxy used: {proxy_used}, Attempt: {attempt_number}/{total_attempts}")
        else:
            if proxy_used != 'none' or attempt_number > 1:
                self.logger.info(f"Playwright API used {proxy_used} proxy (attempt {attempt_number}/{total_attempts})")
        
        # Create HtmlResponse for use in callback
        scrapy_response = HtmlResponse(
            url=url,
            body=html_content.encode('utf-8'),
            encoding='utf-8'
        )
        
        meta = self._build_request_meta()
        meta['playwright_response'] = scrapy_response
        meta['playwright_proxy_used'] = proxy_used
        
        # Add auto-rotate proxy metadata for Playwright requests
        if self.auto_rotate_proxy:
            meta['auto_rotate_proxy'] = True
            meta['original_url'] = url
            meta['proxy_attempt'] = self.proxy_retry_count.get(url, 0) + 1
        
        return scrapy.Request(
            url=url,
            callback=self._parse_wrapper,
            meta=meta,
            dont_filter=True
        )

    def _handle_request_error(self, failure):
        """Enhanced error handler with auto-rotating proxy support."""
        url = failure.request.url
        meta = failure.request.meta

        # Construct detailed error message with proxy information
        status_code = None
        error_text = failure.getErrorMessage()
        current_proxy_info = "No proxy"
        
        # Get current proxy information
        if self.auto_rotate_proxy and self.current_proxy_index < len(self.proxy_rotation_cycle):
            current_proxy_type = self.proxy_rotation_cycle[self.current_proxy_index]
            current_proxy_info = f"{current_proxy_type.value} proxy"
            if self.proxy:
                current_proxy_info += f" ({self.proxy})"

        if hasattr(failure.value, 'response') and failure.value.response is not None:
            status_code = failure.value.response.status
            # Log detailed error with proxy information
            detailed_error_msg = f"Request failed for {url} using {current_proxy_info}: Status {status_code} - {error_text}"
        else:
            # For errors without a response (e.g., DNS lookup, connection refused)
            detailed_error_msg = f"Request failed for {url} using {current_proxy_info}: {error_text}"

        self.logger.error(detailed_error_msg)

        # Log additional details for proxy attempts
        if self.auto_rotate_proxy:
            attempt_number = self.proxy_retry_count.get(url, 0) + 1
            self.logger.info(f"Proxy attempt {attempt_number}/{self.max_proxy_retries} failed for {url}")
            if status_code:
                self.logger.info(f"  - Status Code: {status_code}")
            self.logger.info(f"  - Proxy Type: {current_proxy_info}")
            self.logger.info(f"  - Error: {error_text}")

        if self.debug_mode:
            self.logger.debug(f"Full error details for {url}:", exc_info=failure)

        # Check if this is an auto-rotate proxy request and if we should retry
        if (self.auto_rotate_proxy and 
            meta.get('auto_rotate_proxy') and 
            url not in self.failed_urls_with_all_proxies):
            
            # Check if this is a retryable error
            if hasattr(failure.value, 'response') and failure.value.response:
                response = failure.value.response
                if response.status in self.proxy_rotation_status_codes:
                    if self._rotate_to_next_proxy(url):
                        next_proxy_type = self.proxy_rotation_cycle[self.current_proxy_index]
                        next_proxy = self._get_proxy_for_type(next_proxy_type)
                        self.logger.info(f"Retrying request with {next_proxy_type.value} proxy ({next_proxy}) for: {url}")
                        return self._create_scrapy_request(url, is_retry=True)
            
            # For other types of failures (network errors, etc.)
            elif self._rotate_to_next_proxy(url):
                next_proxy_type = self.proxy_rotation_cycle[self.current_proxy_index]
                next_proxy = self._get_proxy_for_type(next_proxy_type)
                self.logger.info(f"Retrying request with {next_proxy_type.value} proxy ({next_proxy}) due to network error for: {url}")
                return self._create_scrapy_request(url, is_retry=True)
        
        # If not retrying or retries exhausted, handle as normal error
        self.crawl_status = False
        self.error_messages.append(detailed_error_msg) # Store detailed message

    def _parse_wrapper(self, response):
        """
        Enhanced wrapper for parse method with auto-rotating proxy support.
        This prevents dictionary yields from being passed to Scrapy's scheduler.
        """
        current_url_for_error = response.url if response else "Unknown URL"
        try:
            if self.debug_mode:
                self.logger.debug(f"Parse wrapper called for URL: {response.url}")
                self.logger.debug(f"Response status: {response.status}, length: {len(response.body)}")
            
            # Check if this is a Playwright response and use the stored response if available
            playwright_response = response.meta.get('playwright_response')
            actual_response = playwright_response if playwright_response else response
            
            # Check if proxy rotation is needed based on response
            if self._should_rotate_proxy(actual_response):
                url = actual_response.url
                current_proxy_type = self.proxy_rotation_cycle[self.current_proxy_index] if self.auto_rotate_proxy else "unknown"
                
                # Log detailed information about why rotation was triggered
                self.logger.warning(f"Proxy rotation triggered for {url} using {current_proxy_type.value} proxy")
                self.logger.info(f"  - Response Status: {actual_response.status}")
                self.logger.info(f"  - Response Length: {len(actual_response.body)} bytes")
                
                # Check what triggered the rotation
                if actual_response.status in self.proxy_rotation_status_codes:
                    self.logger.info(f"  - Trigger: Status code {actual_response.status} in rotation list")
                else:
                    # Check for IP detection patterns
                    response_text = actual_response.text.lower()
                    found_patterns = [pattern for pattern in self.ip_detection_patterns if pattern in response_text]
                    if found_patterns:
                        self.logger.info(f"  - Trigger: IP detection patterns found: {found_patterns[:3]}...")  # Show first 3 patterns
                    
                    # Check headers
                    headers = actual_response.headers
                    blocking_headers = ['x-blocked', 'x-access-denied']
                    found_headers = [header for header in blocking_headers if header.lower().encode() in headers]
                    if found_headers:
                        self.logger.info(f"  - Trigger: Blocking headers found: {found_headers}")
                
                if url not in self.failed_urls_with_all_proxies and self._rotate_to_next_proxy(url):
                    next_proxy_type = self.proxy_rotation_cycle[self.current_proxy_index]
                    next_proxy = self._get_proxy_for_type(next_proxy_type)
                    self.logger.info(f"Retrying request with {next_proxy_type.value} proxy ({next_proxy}) for: {url}")
                    
                    # For parse wrapper retries, always use Scrapy requests to avoid async issues
                    # Playwright retries are handled within the _create_playwright_request method itself
                    yield self._create_scrapy_request(url, is_retry=True)
                    return
                else:
                    self.logger.error(f"All proxy rotation attempts failed for: {url}")
            
            # Call the actual parse method with the appropriate response
            parse_results = self.parse(actual_response)
            
            # Filter results to only yield proper Request objects
            if parse_results:
                for item in parse_results:
                    # Only yield Request objects or other valid Scrapy items
                    if hasattr(item, 'url') and hasattr(item, 'callback'):
                        # This is a proper Request object
                        if self.debug_mode:
                            self.logger.debug(f"Yielding Request: {item.url}")
                        yield item
                    elif isinstance(item, dict) and 'link' in item:
                        # Old pattern: dictionary with link - skip it
                        # The link should already be sent to Kafka by the spider
                        if self.debug_mode:
                            self.logger.debug(f"Filtered dictionary yield: {item}")
                        continue
                    else:
                        # Other types (items, etc.) - yield as-is
                        if self.debug_mode:
                            self.logger.debug(f"Yielding item: {type(item)}")
                        yield item
                        
        except Exception as e:
            # Construct a simplified message for parsing errors
            error_message_for_log = f"Error in parse wrapper for {current_url_for_error}: {str(e)}"
            self.logger.error(error_message_for_log)

            if self.debug_mode:
                self.logger.debug(f"Parse wrapper exception details for {current_url_for_error}:", exc_info=True)

            self.crawl_status = False
            self.error_messages.append(error_message_for_log)

    def parse(self, response):
        """
        Parse method to be implemented by subclasses.
        
        Args:
            response: Scrapy response object
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement the 'parse' method.")

    def create_url_item(self, url: str, response, **extra_fields) -> URLDiscoveryItem:
        """
        Create a standardized URLDiscoveryItem with common fields populated.
        
        Args:
            url: The discovered URL
            response: The Scrapy response object
            **extra_fields: Additional fields to set on the item
            
        Returns:
            URLDiscoveryItem: Properly initialized item
        """
        base_fields = {
            'url': url,
            'referer_url': response.url,
            'source_domain': urlparse(url).netloc,
            'response_status': response.status,
            'worker_id': self.worker_id,
            'depth': response.meta.get('depth', 0),
        }
        
        # Merge with extra fields
        base_fields.update(extra_fields)
        
        return URLDiscoveryItem(**base_fields)

    async def process_next_page(self, next_page_url: Optional[str], response):
        """
        Process next page with proper async request creation.
        
        Args:
            next_page_url: URL of the next page
            response: Current response object
            
        Yields:
            Scrapy Request for the next page
        """
        if not self._should_process_next_page(next_page_url):
            return

        self.logger.info(f'Processing next page: {next_page_url}')
        self.page_number += 1
        
        if self.use_playwright_request:
            async for request in self._create_playwright_request(next_page_url):
                yield request
        else:
            yield self._create_scrapy_request(next_page_url)

    def _should_process_next_page(self, next_page_url: Optional[str]) -> bool:
        """
        Check if next page should be processed.
        
        Args:
            next_page_url: URL of the next page
            
        Returns:
            bool: True if next page should be processed
        """
        return (
            next_page_url is not None and 
            self.page_number < self.page_request
        )

    def closed(self, reason: str):
        """
        Handle spider closure and log final stats.
        
        Args:
            reason: Reason for spider closure
        """
        elapsed_time = time.time() - self.start_time
        self.logger.info(f"Crawl completed in {elapsed_time:.2f} seconds.")
        self.logger.info(f'Spider closed: {reason}')
        
        # Log final statistics
        self._log_final_stats(elapsed_time, reason)

    def _log_final_stats(self, elapsed_time: float, reason: str):
        """
        Log final crawling statistics.
        
        Args:
            elapsed_time: Total time spent crawling
            reason: Reason for spider closure
        """
        if self.debug_mode:
            self.logger.debug(f"Final stats - Elapsed time: {elapsed_time:.2f}s, Reason: {reason}")