# POSTGRES
PG_HOST = "localhost"
PG_DATABASE = "onm"
PG_USER = "onm_admin"
PG_PASSWORD = "onmdb"
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
BOOTSTRAP_SERVER = '139.59.241.75:9092'
VPS_SERVER = '195.35.22.151'
PRODUCTION_SERVER_1 = '10.130.137.101:9092'
PRODUCTION_SERVER_2 = '10.130.137.99:9092'
PRODUCTION_SERVER_3 = '10.130.137.100:9092'

# API
CREATE_ARTICLE_ENDPOINT = 'https://v5.external.dashboard.nolimit.id/online-media/raw-uri/create'
SEND_POST_ARTICLE_ENDPOINT = 'https://external.backend.dashboard.nolimit.id/online-media/raw-article/create' 
API_ZYTE = '0c671085bb1743bf94aca63032c28ceb'

# PROXY
LOCAL_PROXY = 'http://bandung:456xyz@proxycrawler.dashboard.nolimit.id:2570'
ZYTE_PROXY = 'http://0c671085bb1743bf94aca63032c28ceb:@api.zyte.com:8011'