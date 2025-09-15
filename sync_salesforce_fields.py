import subprocess
import json
import pyodbc
from datetime import datetime
from dotenv import load_dotenv
import os

# Load .env
load_dotenv()

# Env vars
sql_driver = os.getenv("SQL_DRIVER")
sql_server = os.getenv("SQL_SERVER")
sql_db = os.getenv("SQL_DATABASE")
sql_user = os.getenv("SQL_USERNAME")
sql_pwd = os.getenv("SQL_PASSWORD")
org = os.getenv("SALESFORCE_ORG")
sf_cli = os.getenv("SF_CLI", "sf.cmd")  # Default to sf.cmd on Windows

# SQL Connection
cn = pyodbc.connect(
    f"DRIVER={sql_driver};"
    f"SERVER={sql_server};"
    f"DATABASE={sql_db};"
    f"UID={sql_user};"
    f"PWD={sql_pwd}"
)
cur = cn.cursor()

def ensure_table():
    """Create SalesforceFields table if it does not exist"""
    cur.execute("""
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SalesforceFields' AND xtype='U')
    CREATE TABLE SalesforceFields (
        ObjectName NVARCHAR(255),
        FieldName NVARCHAR(255),
        FieldLabel NVARCHAR(255),
        DataType NVARCHAR(255),
        LastSeen DATETIME NOT NULL,
        IsDeleted BIT NOT NULL DEFAULT 0,
        PRIMARY KEY (ObjectName, FieldName)
    );
    """)
    cn.commit()

def get_objects():
    result = subprocess.run(
        [sf_cli, "sobject", "list", "--json", "--target-org", org],
        capture_output=True, text=True, shell=True
    )
    data = json.loads(result.stdout)
    return data.get("result", [])

def get_fields(object_name):
    result = subprocess.run(
        [sf_cli, "sobject", "describe", "--sobject-name", object_name, "--json", "--target-org", org],
        capture_output=True, text=True, shell=True
    )
    return json.loads(result.stdout).get("fields", [])

def mark_all_deleted():
    cur.execute("UPDATE SalesforceFields SET IsDeleted = 1")
    cn.commit()

def upsert_field(obj, name, label, dtype):
    now = datetime.utcnow()
    cur.execute("""
    MERGE SalesforceFields AS target
    USING (SELECT ? AS ObjectName, ? AS FieldName) AS src
    ON target.ObjectName = src.ObjectName AND target.FieldName = src.FieldName
    WHEN MATCHED THEN
        UPDATE SET FieldLabel=?, DataType=?, LastSeen=?, IsDeleted=0
    WHEN NOT MATCHED THEN
        INSERT (ObjectName, FieldName, FieldLabel, DataType, LastSeen, IsDeleted)
        VALUES (?, ?, ?, ?, ?, 0);
    """, obj, name, label, dtype, now, obj, name, label, dtype, now)
    cn.commit()

def main():
    ensure_table()   # ✅ make sure table exists first
    mark_all_deleted()
    objects = get_objects()
    print(f"🔹 Found {len(objects)} objects")

    for obj in objects:
        print(f"⏳ Processing {obj}")
        fields = get_fields(obj)
        for f in fields:
            name = f.get("name")
            label = f.get("label")
            dtype = f.get("type")
            upsert_field(obj, name, label, dtype)

    print("✅ Sync complete")

if __name__ == "__main__":
    main()
