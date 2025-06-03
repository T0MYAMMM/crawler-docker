from crawler.registry import SpiderRegistry
import yaml
import os

def create_spider(domain, config_path=None):
    """Create a spider instance for the given domain."""
    spider_class = SpiderRegistry.get_spider(domain)
    
    if not spider_class:
        raise ValueError(f"No spider registered for domain {domain}")
    
    # Load configuration if provided
    config = {}
    if config_path:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    
    return spider_class(config=config)

def create_all_spiders(config_dir='config/spiders'):
    """Create all spider instances from configuration directory."""
    spiders = []
    
    for root, dirs, files in os.walk(config_dir):
        for file in files:
            if file.endswith('.yml'):
                domain = file.split('.')[0]
                config_path = os.path.join(root, file)
                try:
                    spider = create_spider(domain, config_path)
                    spiders.append(spider)
                except ValueError:
                    # Log missing spider implementation
                    pass
    
    return spiders