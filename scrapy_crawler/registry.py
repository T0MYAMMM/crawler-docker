class SpiderRegistry:
    """Registry for spider classes that can be dynamically loaded."""
    
    _spiders = {}
    
    @classmethod
    def register(cls, spider_class):
        """Register a spider class."""
        domain = getattr(spider_class, 'domain', None)
        if domain:
            cls._spiders[domain] = spider_class
        return spider_class
    
    @classmethod
    def get_spider(cls, domain):
        """Get spider class for a specific domain."""
        return cls._spiders.get(domain)
    
    @classmethod
    def get_all_spiders(cls):
        """Get all registered spider classes."""
        return cls._spiders.copy()