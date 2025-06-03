# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import json
import logging
from datetime import datetime
from typing import Dict, Any
from urllib.parse import urlparse
from itemadapter import ItemAdapter
from kafka import KafkaProducer
from kafka.errors import KafkaError

from utils.kafka_utils import json_serializer, send_url
from config.settings import (
    PRODUCTION_SERVER_1, 
    PRODUCTION_SERVER_2, 
    PRODUCTION_SERVER_3
)


class ItemEnrichmentPipeline:
    """
    Pipeline to enrich items with additional metadata and normalize fields.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Add extraction timestamp if not present
        if not adapter.get('extracted_at'):
            adapter['extracted_at'] = datetime.utcnow().isoformat()
        
        # Extract and set domain if not present
        if adapter.get('url') and not adapter.get('source_domain'):
            parsed_url = urlparse(adapter['url'])
            adapter['source_domain'] = parsed_url.netloc
        
        # Set spider name
        adapter['spider_name'] = spider.name
        
        # Set user agent from spider settings
        if hasattr(spider, 'settings') and not adapter.get('user_agent'):
            user_agent = spider.settings.get('USER_AGENT')
            if user_agent:
                adapter['user_agent'] = user_agent
        
        # Normalize URL (remove trailing slashes, etc.)
        if adapter.get('url'):
            adapter['url'] = self._normalize_url(adapter['url'])
        
        # Set default values for missing fields
        self._set_defaults(adapter, spider)
        
        self.logger.debug(f"Enriched item: {adapter['url']}")
        return item
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to standard format."""
        url = url.strip()
        if url.endswith('/') and len(url) > 1:
            url = url[:-1]
        return url
    
    def _set_defaults(self, adapter: ItemAdapter, spider):
        """Set default values for missing fields."""
        defaults = {
            'depth': 0,
            'priority': 0,
            'is_article': False,
            'content_type': 'unknown',
            'response_status': 200,
        }
        
        for key, default_value in defaults.items():
            if not adapter.get(key):
                adapter[key] = default_value


class DuplicationFilterPipeline:
    """
    Pipeline to filter duplicate URLs within the same spider run.
    Silently ignores duplicates without raising exceptions to avoid error logs.
    """
    
    def __init__(self):
        self.seen_urls = set()
        self.duplicate_count = 0
        self.processed_count = 0
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        url = adapter.get('url')
        
        if not url:
            self.logger.warning("Item without URL found, ignoring item")
            return None  # Silently ignore instead of raising exception
        
        self.processed_count += 1
        
        if url in self.seen_urls:
            self.duplicate_count += 1
            
            # Only log duplicates in debug mode to reduce noise
            if hasattr(spider, 'debug_mode') and spider.debug_mode:
                self.logger.debug(f"Duplicate URL ignored (#{self.duplicate_count}): {url}")
            
            # Log every 25th duplicate to show progress without spam
            elif self.duplicate_count % 25 == 0:
                self.logger.info(f"Filtered {self.duplicate_count} duplicate URLs so far")
            
            return None  # Silently ignore duplicate instead of raising exception
        
        self.seen_urls.add(url)
        
        # Log progress every 50 unique URLs
        if len(self.seen_urls) % 50 == 0:
            self.logger.info(f"Processed {len(self.seen_urls)} unique URLs")
        
        return item
    
    def close_spider(self, spider):
        """Log final duplication statistics when spider closes."""
        unique_count = len(self.seen_urls)
        total_processed = self.processed_count
        duplicate_rate = (self.duplicate_count / total_processed * 100) if total_processed > 0 else 0
        
        self.logger.info(
            f"Duplication Filter Summary for {spider.name}: "
            f"Unique URLs: {unique_count}, "
            f"Duplicates: {self.duplicate_count}, "
            f"Total processed: {total_processed}, "
            f"Duplicate rate: {duplicate_rate:.1f}%"
        )


class KafkaURLPipeline:
    """
    Pipeline to send discovered URLs to Kafka for further processing.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.producer = None
        self.sent_count = 0
        self.failed_count = 0
    
    def open_spider(self, spider):
        """Initialize Kafka producer when spider starts."""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=[
                    PRODUCTION_SERVER_1, 
                    PRODUCTION_SERVER_2, 
                    PRODUCTION_SERVER_3
                ],
                value_serializer=json_serializer,
                retries=3,
                acks='all',
                compression_type='gzip',
                request_timeout_ms=30000,
            )
            self.logger.info(f"Kafka producer initialized for spider {spider.name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka producer: {e}")
            self.producer = None
    
    def process_item(self, item, spider):
        """Send item to Kafka topic."""
        # Skip None items (filtered duplicates)
        if item is None:
            return None
            
        if not self.producer:
            self.logger.warning("Kafka producer not available, skipping item")
            return item
        
        adapter = ItemAdapter(item)
        
        # Prepare data for Kafka
        kafka_data = {
            'link': adapter.get('url'),
            'source_domain': adapter.get('source_domain'),
            'referer_url': adapter.get('referer_url'),
            'spider_name': adapter.get('spider_name'),
            'extracted_at': adapter.get('extracted_at'),
            'is_article': adapter.get('is_article', False),
            'priority': adapter.get('priority', 0),
            'search_phrases': adapter.get('search_phrases'),
            'worker_id': adapter.get('worker_id'),
            'depth': adapter.get('depth', 0),
        }
        
        # Remove None values
        kafka_data = {k: v for k, v in kafka_data.items() if v is not None}
        
        # Send to Kafka
        success = send_url(kafka_data, self.producer, topic='onm-urls')
        
        if success:
            self.sent_count += 1
            if hasattr(spider, 'debug_mode') and spider.debug_mode:
                self.logger.debug(f"Sent to Kafka: {adapter.get('url')}")
        else:
            self.failed_count += 1
            self.logger.error(f"Failed to send to Kafka: {adapter.get('url')}")
        
        return item
    
    def close_spider(self, spider):
        """Clean up Kafka producer when spider closes."""
        self.logger.info(
            f"Kafka pipeline stats for {spider.name}: "
            f"sent={self.sent_count}, failed={self.failed_count}"
        )
        
        if self.producer:
            try:
                self.producer.flush(timeout=30)
                self.producer.close(timeout=30)
                self.logger.info("Kafka producer closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing Kafka producer: {e}")


class MetricsPipeline:
    """
    Pipeline to collect and save crawler metrics.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.stats = {
            'total_items': 0,
            'articles_found': 0,
            'domains_processed': set(),
            'depths': {},
        }
    
    def process_item(self, item, spider):
        """Collect metrics from processed items."""
        # Skip None items (filtered duplicates)
        if item is None:
            return None
            
        adapter = ItemAdapter(item)
        
        self.stats['total_items'] += 1
        
        if adapter.get('is_article'):
            self.stats['articles_found'] += 1
        
        if adapter.get('source_domain'):
            self.stats['domains_processed'].add(adapter['source_domain'])
        
        depth = adapter.get('depth', 0)
        self.stats['depths'][depth] = self.stats['depths'].get(depth, 0) + 1
        
        # Log progress periodically
        if self.stats['total_items'] % 100 == 0:
            self.logger.info(f"Processed {self.stats['total_items']} items")
        
        return item
    
    def close_spider(self, spider):
        """Log final metrics when spider closes."""
        stats_summary = {
            'spider_name': spider.name,
            'total_items': self.stats['total_items'],
            'articles_found': self.stats['articles_found'],
            'unique_domains': len(self.stats['domains_processed']),
            'depth_distribution': dict(self.stats['depths']),
            'domains_list': list(self.stats['domains_processed']),
        }
        
        self.logger.info(f"Final metrics for {spider.name}: {json.dumps(stats_summary)}")
        
        # Store metrics for external consumption
        if hasattr(spider, 'crawler') and hasattr(spider.crawler, 'stats'):
            for key, value in stats_summary.items():
                spider.crawler.stats.set_value(f'pipeline_metrics/{key}', value)
