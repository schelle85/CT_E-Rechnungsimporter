import os
from pathlib import Path
from sqlalchemy import URL, create_engine

def make_engine():
    password = Path(os.environ.get("DB_PASSWORD_FILE", "/run/secrets/db_password")).read_text().rstrip("\r\n")
    return create_engine(URL.create(
        "mysql+pymysql", username=os.environ.get("DB_USER", "importer"),
        password=password, host=os.environ.get("DB_HOST", "db"),
        database=os.environ.get("DB_NAME", "importer"),
    ), pool_pre_ping=True, pool_recycle=300, connect_args={"connect_timeout": 3, "read_timeout": 5, "write_timeout": 5})
