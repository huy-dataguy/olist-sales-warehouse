"""Read a secret without putting its value into Compose or command arguments."""
import os
from pathlib import Path
import sys

os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"] = Path("/run/secrets/airflow_connection").read_text().strip()
os.execv("/entrypoint", ["/entrypoint", "airflow", *sys.argv[1:]])
