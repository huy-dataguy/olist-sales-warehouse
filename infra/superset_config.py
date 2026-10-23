"""Single-host demo Superset. Business SQL is pinned to validated releases."""
import json
from pathlib import Path
from urllib.parse import quote_plus

cfg = json.loads(Path('/run/secrets/superset.json').read_text())
SECRET_KEY = cfg['secret_key']
SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://salesdw_superset:' + quote_plus(cfg['metadata_password']) + '@postgres:5432/superset_meta'
SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_size': 5, 'max_overflow': 5}
APP_NAME = 'SalesDW · Olist Analytics'
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = None
FEATURE_FLAGS = {'ENABLE_TEMPLATE_PROCESSING': False, 'DASHBOARD_CROSS_FILTERS': True}
DATA_CACHE_CONFIG = {'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300}
CACHE_CONFIG = {'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300}
FILTER_STATE_CACHE_CONFIG = {'CACHE_TYPE': 'SupersetMetastoreCache', 'CACHE_DEFAULT_TIMEOUT': 86400}
EXPLORE_FORM_DATA_CACHE_CONFIG = {'CACHE_TYPE': 'SupersetMetastoreCache', 'CACHE_DEFAULT_TIMEOUT': 86400}
SQLLAB_TIMEOUT = 120
SUPERSET_WEBSERVER_TIMEOUT = 120
ROW_LIMIT = 50000
ENABLE_PROXY_FIX = False
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_HTTPONLY = True
TALISMAN_ENABLED = False  # HTTP loopback only; no external exposure in this demo.
DEFAULT_TIME_FILTER = 'No filter'

