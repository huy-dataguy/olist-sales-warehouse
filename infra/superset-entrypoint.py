"""App metadata migrations run only from the explicit Compose init service."""
import json
import os
from pathlib import Path
import subprocess
import sys

if len(sys.argv) > 1 and sys.argv[1] == 'init':
    if os.environ.get('SALES_DW_SUPERSET_MIGRATION_APPROVED') != 'salesdw':
        raise SystemExit('Use the designated salesdw Superset init service')
    subprocess.run(['superset', 'db', 'upgrade'], check=True)
    subprocess.run(['superset', 'init'], check=True)
    from superset.app import create_app
    from superset.extensions import appbuilder
    account = json.loads(Path('/run/secrets/superset_admin.json').read_text())
    with create_app().app_context():
        manager = appbuilder.sm
        if manager.find_user(username=account['username']) is None:
            assert manager.add_user(account['username'], account['first_name'], account['last_name'], account['email'], manager.find_role('Admin'), account['password'])
    print('Superset metadata initialized; demo account ready (password redacted).')
else:
    os.execvp('gunicorn', ['gunicorn', '--bind', '0.0.0.0:8088', '--workers', '2', '--worker-class', 'gthread', '--threads', '4', '--timeout', '120', '--access-logfile', '-', 'superset.app:create_app()'])
