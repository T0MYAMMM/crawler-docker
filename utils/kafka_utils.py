"""
Kafka Producer for Crawler URLs

This module provides functionality to send discovered URLs from web crawlers
to Kafka topics for further processing by the ONM system.

Author: ONM Development Team
Created: 2025
"""

import json
import logging
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError, KafkaTimeoutError

# Configure module-level logger
logger = logging.getLogger(__name__)


def json_serializer(data: Dict[str, Any]) -> bytes:
    """
    Serialize dictionary data to JSON bytes for Kafka transmission.
    
    Args:
        data: Dictionary containing data to serialize
        
    Returns:
        bytes: JSON-encoded data as bytes
        
    Raises:
        TypeError: If data is not JSON serializable
    """
    try:
        return json.dumps(data, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to serialize data to JSON: {data}. Error: {e}")
        raise

def send_url(data: Dict[str, Any], producer: KafkaProducer, topic: str = 'onm-urls') -> bool:
    """
    Send URL data to Kafka topic for processing.
    
    This function sends discovered URLs from web crawlers to the Kafka message queue
    where they will be consumed by the crawler client for database storage.
    
    Args:
        data: Dictionary containing URL data with required 'link' key
        producer: Configured KafkaProducer instance
        topic: Kafka topic name (default: 'onm-urls')
        
    Returns:
        bool: True if message was sent successfully, False otherwise
        
    Raises:
        ValueError: If data is missing required fields
        KafkaError: If Kafka operation fails
        
    Example:
        >>> producer = KafkaProducer(...)
        >>> url_data = {'link': 'https://example.com/article'}
        >>> success = send_url(url_data, producer)
        >>> print(f"URL sent: {success}")
    """
    # Validate input data
    if not isinstance(data, dict):
        raise ValueError(f"Data must be a dictionary, got {type(data)}")
    
    if 'link' not in data:
        raise ValueError("Data must contain 'link' key")
    
    if not data['link'] or not isinstance(data['link'], str):
        raise ValueError("Link must be a non-empty string")
    
    url = data['link']
    
    try:
        logger.info(f"Sending URL to Kafka topic '{topic}': {url}")
        
        # Send message to Kafka
        future = producer.send(topic, value=data)
        
        # Wait for confirmation with timeout
        record_metadata = future.get(timeout=10)
        
        # Ensure message is sent immediately
        producer.flush()
        
        logger.info(
            f"Successfully sent URL to topic '{topic}' "
            f"(partition: {record_metadata.partition}, "
            f"offset: {record_metadata.offset}): {url}"
        )
        
        return True
        
    except KafkaTimeoutError as e:
        logger.error(f"Timeout while sending URL to Kafka: {url}. Error: {e}")
        return False
        
    except KafkaError as e:
        logger.error(f"Kafka error while sending URL: {url}. Error: {e}")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error while sending URL to Kafka: {url}. Error: {e}")
        return False

def create_producer(
    bootstrap_servers: list,
    retries: int = 3,
    batch_size: int = 16384,
    linger_ms: int = 10,
    buffer_memory: int = 33554432,
    max_request_size: int = 1048576
) -> Optional[KafkaProducer]:
    """
    Create and configure a Kafka producer instance.
    
    Args:
        bootstrap_servers: List of Kafka broker addresses
        retries: Number of retries for failed sends (default: 3)
        batch_size: Batch size in bytes (default: 16384)
        linger_ms: Time to wait for additional messages (default: 10ms)
        buffer_memory: Total memory available for buffering (default: 32MB)
        max_request_size: Maximum size of a request (default: 1MB)
        
    Returns:
        KafkaProducer: Configured producer instance or None if creation fails
        
    Example:
        >>> servers = ['localhost:9092', 'localhost:9093']
        >>> producer = create_producer(servers)
        >>> if producer:
        ...     send_url({'link': 'https://example.com'}, producer)
    """
    try:
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=json_serializer,
            retries=retries,
            batch_size=batch_size,
            linger_ms=linger_ms,
            buffer_memory=buffer_memory,
            max_request_size=max_request_size,
            acks='all',  # Wait for all replicas to acknowledge
            compression_type='gzip',  # Compress messages
            request_timeout_ms=30000,  # 30 second timeout
            retry_backoff_ms=100,  # Backoff between retries
        )
        
        logger.info(f"Kafka producer created successfully with servers: {bootstrap_servers}")
        return producer
        
    except Exception as e:
        logger.error(f"Failed to create Kafka producer: {e}")
        return None


def close_producer(producer: KafkaProducer, timeout: int = 30) -> bool:
    """
    Safely close Kafka producer with proper cleanup.
    
    Args:
        producer: KafkaProducer instance to close
        timeout: Maximum time to wait for pending messages (seconds)
        
    Returns:
        bool: True if closed successfully, False otherwise
    """
    try:
        if producer:
            logger.info("Closing Kafka producer...")
            producer.flush(timeout=timeout)
            producer.close(timeout=timeout)
            logger.info("Kafka producer closed successfully")
            return True
    except Exception as e:
        logger.error(f"Error closing Kafka producer: {e}")
        return False
    
    return False

