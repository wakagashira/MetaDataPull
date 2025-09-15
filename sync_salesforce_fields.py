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
sf_cli = os.getenv("SF_CLI", "sf.cmd")

# SQL Connection (autocommit True for safety)
cn = pyodbc.connect(
    f"DRIVER={sql_driver};"
    f"SERVER={sql_server};"
    f"DATABASE={sql_db};"
    f"UID={sql_user};"
    f"PWD={sql_pwd}",
    autocommit=True
)
cur = cn.cursor()

def ensure_field_table():
    cur.execute("""
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SalesforceFields' AND xtype='U')
    CREATE TABLE SalesforceFields (
        ObjectName NVARCHAR(255),
        FieldName NVARCHAR(255),
        FieldLabel NVARCHAR(255),
        DataType NVARCHAR(255),
        LastSeen DATETIME NOT NULL,
        LastUpdatedInSF DATETIME NULL,
        IsDeleted BIT NOT NULL DEFAULT 0,
        PRIMARY KEY (ObjectName, FieldName)
    );
    """)
    # Ensure LastUpdatedInSF column exists
    try:
        cur.execute("ALTER TABLE SalesforceFields ADD LastUpdatedInSF DATETIME NULL;")
    except Exception:
        pass

def run_sf_command(cmd_args):
    result = subprocess.run(cmd_args, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print(f"⚠️ CLI command failed: {' '.join(cmd_args)}")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return {}
    try:
        return json.loads(result.stdout)
    except Exception as e:
        print("⚠️ Failed to parse JSON:", e)
        print("Output was:", result.stdout[:500])
        return {}

def get_objects():
    data = run_sf_command([sf_cli, "force", "schema", "sobject", "list", "--json", "--target-org", org])
    return data.get("result", [])

def get_fields(object_name):
    data = run_sf_command([sf_cli, "force", "schema", "sobject", "describe", "-s", object_name, "--json", "--target-org", org])
    return data.get("result", {}).get("fields", [])

def mark_all_deleted():
    cur.execute("UPDATE SalesforceFields SET IsDeleted = 1")

def upsert_field(obj, name, label, dtype):
    now = datetime.utcnow()
    label = label or ""
    dtype = dtype or ""

    # Check if field exists
    cur.execute("""
        SELECT FieldLabel, DataType
        FROM SalesforceFields
        WHERE ObjectName=? AND FieldName=?
    """, (obj, name))
    row = cur.fetchone()

    if row:
        old_label, old_dtype = row
        if old_label != label or old_dtype != dtype:
            cur.execute("""
                UPDATE SalesforceFields
                SET FieldLabel=?, DataType=?, LastSeen=?, IsDeleted=0, LastUpdatedInSF=?
                WHERE ObjectName=? AND FieldName=?
            """, (label, dtype, now, now, obj, name))
            print(f"   UPDATED -> {obj}.{name} | Label={label} | Type={dtype}")
        else:
            cur.execute("""
                UPDATE SalesforceFields
                SET LastSeen=?, IsDeleted=0
                WHERE ObjectName=? AND FieldName=?
            """, (now, obj, name))
    else:
        cur.execute("""
            INSERT INTO SalesforceFields (ObjectName, FieldName, FieldLabel, DataType, LastSeen, LastUpdatedInSF, IsDeleted)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (obj, name, label, dtype, now, now))
        print(f"   INSERT -> {obj}.{name} | Label={label} | Type={dtype}")

def main():
    ensure_field_table()

    mark_all_deleted()
    objects = get_objects()
    print(f"🔹 Found {len(objects)} objects")

    for idx, obj in enumerate(objects, start=1):
        print(f"⏳ Processing {idx}/{len(objects)}: {obj}")
        fields = get_fields(obj)
        if not fields:
            print(f"⚠️ No fields returned for {obj}")
        for f in fields:
            name = f.get("name")
            label = f.get("label")
            dtype = f.get("type")
            upsert_field(obj, name, label, dtype)

    print("✅ Field sync complete")
    print("⚠️ Skipping MetadataComponentDependency (not available in this CLI).")

if __name__ == "__main__":
    main()
