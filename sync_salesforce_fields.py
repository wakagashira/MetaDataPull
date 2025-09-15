import subprocess
import json
import pyodbc
from datetime import datetime
from dotenv import load_dotenv
import os
import requests

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
api_version = os.getenv("SF_API_VERSION", "61.0")

# Control flags
sync_fields = os.getenv("SYNC_FIELDS", "true").lower() == "true"
sync_usage = os.getenv("SYNC_USAGE", "true").lower() == "true"

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
    try:
        cur.execute("ALTER TABLE SalesforceFields ADD LastUpdatedInSF DATETIME NULL;")
    except Exception:
        pass

def ensure_usage_table():
    cur.execute("""
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SalesforceFieldUsage' AND xtype='U')
    CREATE TABLE SalesforceFieldUsage (
        MetadataComponentType NVARCHAR(255),
        MetadataComponentName NVARCHAR(255),
        RefMetadataComponentType NVARCHAR(255),
        RefMetadataComponentName NVARCHAR(255),
        LastSeen DATETIME NOT NULL,
        PRIMARY KEY (MetadataComponentType, MetadataComponentName, RefMetadataComponentName)
    );
    """)

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

def get_cli_auth():
    data = run_sf_command([sf_cli, "org", "display", "--json", "--target-org", org])
    result = data.get("result", {}) if data else {}
    access_token = result.get("accessToken")
    instance_url = result.get("instanceUrl")
    if not access_token or not instance_url:
        raise RuntimeError("Could not obtain access token/instance URL from Salesforce CLI.")
    return access_token, instance_url

def tooling_query_all(soql, access_token, instance_url):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    url = f"{instance_url}/services/data/v{api_version}/tooling/query"
    params = {"q": soql}
    out = []

    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"Tooling API query failed: {resp.status_code} {resp.text}")
    data = resp.json()
    out.extend(data.get("records", []))

    while data.get("done") is False and data.get("nextRecordsUrl"):
        next_url = instance_url + data["nextRecordsUrl"]
        resp = requests.get(next_url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Tooling API next page failed: {resp.status_code} {resp.text}")
        data = resp.json()
        out.extend(data.get("records", []))

    return out

def sync_field_usage():
    ensure_usage_table()
    try:
        access_token, instance_url = get_cli_auth()
    except Exception as e:
        print(f"⚠️ Skipping MetadataComponentDependency (auth error): {e}")
        return

    soql = (
        "SELECT MetadataComponentName, MetadataComponentType, "
        "RefMetadataComponentName, RefMetadataComponentType "
        "FROM MetadataComponentDependency"
    )
    try:
        records = tooling_query_all(soql, access_token, instance_url)
    except Exception as e:
        print(f"⚠️ Skipping MetadataComponentDependency (query error): {e}")
        return

    print(f"🔹 Found {len(records)} field usage dependencies")    

    now = datetime.utcnow()
    for r in records:
        mtype = r.get("MetadataComponentType") or ""
        mname = r.get("MetadataComponentName") or ""
        rtype = r.get("RefMetadataComponentType") or ""
        rname = r.get("RefMetadataComponentName") or ""

        cur.execute("""
            UPDATE SalesforceFieldUsage
            SET RefMetadataComponentType=?, LastSeen=?
            WHERE MetadataComponentType=? AND MetadataComponentName=? AND RefMetadataComponentName=?
        """, (rtype, now, mtype, mname, rname))

        if cur.rowcount <= 0:
            cur.execute("""
                INSERT INTO SalesforceFieldUsage
                (MetadataComponentType, MetadataComponentName, RefMetadataComponentType, RefMetadataComponentName, LastSeen)
                VALUES (?, ?, ?, ?, ?)
            """, (mtype, mname, rtype, rname, now))

def main():
    ensure_field_table()
    ensure_usage_table()

    if sync_fields:
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
    else:
        print("⚠️ Skipping field sync (SYNC_FIELDS=false)")

    if sync_usage:
        sync_field_usage()
        print("✅ Field usage sync complete")
    else:
        print("⚠️ Skipping field usage sync (SYNC_USAGE=false)")

if __name__ == "__main__":
    main()
