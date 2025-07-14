# POSTGRES
import os

PG_HOST = os.getenv('PG_HOST', '172.17.0.1')
PG_DATABASE = os.getenv('PG_DATABASE', 'onm')
PG_USER = os.getenv('PG_USER', 'onm_admin')
PG_PASSWORD = os.getenv('PG_PASSWORD', 'onmdb')
PG_PORT = int(os.getenv('PG_PORT', '15433'))

URLS_TABLE = 'onm_urls_new'
PHRASES_TABLE = 'onm_phrases'
PROJECTS_TABLE = 'onm_projects'
CONTENTS_TABLE = 'onm_contents'
PROJECTS_PHRASES_TABLE = 'onm_projects_phrases'
WORKERS_PHRASES_TABLE = 'onm_workers_phrases'

# PATH
PATH_CRAWLER_LOG = '/mnt/data/log'
PATH_CRAWLER_METRICS = '/mnt/data/metrics'
PATH_CRAWLER_DAILY_DATA = '/data' # project_dir / data

# KAFKA
BOOTSTRAP_SERVER = ''
VPS_SERVER = ''
PRODUCTION_SERVER_1 = ''
PRODUCTION_SERVER_2 = ''
PRODUCTION_SERVER_3 = ''

# API
CREATE_ARTICLE_ENDPOINT = ''
SEND_POST_ARTICLE_ENDPOINT = '' 
API_ZYTE = ''

# PROXY
LOCAL_PROXY = ''
ZYTE_PROXY = ''

# HEADLESS BROWSER
PLAYWRIGHT_BROWSER_API = ''
