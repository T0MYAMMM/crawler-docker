"""
Time conversion utilities for the crawler system.
"""

from datetime import datetime
import pytz


def convert_utc_to_wib_iso8601(timestamp_str: str) -> str:
    """
    Convert UTC timestamp to WIB (Western Indonesian Time) ISO8601 format.
    
    Args:
        timestamp_str: UTC timestamp string in format "%Y-%m-%dT%H:%M:%S"
        
    Returns:
        ISO8601 formatted timestamp in WIB timezone
    """
    try:
        # Parse the input timestamp
        if isinstance(timestamp_str, str):
            utc_dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
        else:
            utc_dt = timestamp_str
        
        # Set UTC timezone
        utc_dt = pytz.utc.localize(utc_dt) if utc_dt.tzinfo is None else utc_dt
        
        # Convert to WIB (UTC+7)
        wib_tz = pytz.timezone('Asia/Jakarta')
        wib_dt = utc_dt.astimezone(wib_tz)
        
        # Return ISO8601 format
        return wib_dt.isoformat()
        
    except Exception as e:
        # Fallback: return current time in WIB
        wib_tz = pytz.timezone('Asia/Jakarta')
        return datetime.now(wib_tz).isoformat() 