import subprocess
import pyodbc
from datetime import datetime
from dotenv import load_dotenv
import os
import sys
import xml.etree.ElementTree as ET
import shutil
import re

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
keep_flow_xml = os.getenv("KEEP_FLOW_XML", "false").lower() == "true"
debug_flow_parse = os.getenv("DEBUG_FLOW_PARSE", "false").lower() == "true"

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

def ensure_flow_usage_table():
    cur.execute("""
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SalesforceFlowFieldUsage' AND xtype='U')
    CREATE TABLE SalesforceFlowFieldUsage (
        FlowName NVARCHAR(255),
        FlowStatus NVARCHAR(50),
        FieldName NVARCHAR(255),
        LastSeen DATETIME NOT NULL,
        PRIMARY KEY (FlowName, FieldName)
    );
    """)

def sync_flow_field_usage():
    ensure_flow_usage_table()

    # Retrieve all flows via CLI
    print("⏳ Retrieving flows via sf force source retrieve...")
    subprocess.run([sf_cli, "force", "source", "retrieve", "-m", "Flow", "--json", "--target-org", org],
                   capture_output=True, text=True, shell=True)

    flow_dir = os.path.join("force-app", "main", "default", "flows")
    if not os.path.exists(flow_dir):
        print("⚠️ No flows retrieved.")
        return

    now = datetime.utcnow()
    flow_files = [f for f in os.listdir(flow_dir) if f.endswith(".flow-meta.xml")]
    print(f"🔹 Found {len(flow_files)} flow files to parse")    

    field_pattern = re.compile(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+|[A-Za-z0-9_]+__c")    

    for file in flow_files:
        flow_path = os.path.join(flow_dir, file)
        flow_name = file.replace(".flow-meta.xml", "")
        flow_status = "Unknown"
        try:
            tree = ET.parse(flow_path)
            root = tree.getroot()

            # Detect namespace
            ns = {}
            if root.tag.startswith("{"):
                uri = root.tag.split("}")[0].strip("{")
                ns = {"sf": uri}

            status_node = root.find("sf:status", ns) if ns else root.find("status")
            if status_node is not None and status_node.text:
                flow_status = status_node.text

            refs = []

            tags_to_check = [
                "field",
                "conditionField",
                "leftValueReference",
                "rightValueReference",
                "inputAssignments/field",
                "outputAssignments/field",
                "assignmentItems/field",
                "formula",
                "value"
            ]

            for tag in tags_to_check:
                path = f"sf:{tag}" if ns else tag
                for node in root.findall(f".//{path}", ns):
                    if node.text:
                        if debug_flow_parse:
                            print(f"[{flow_name}] {tag}: {node.text}")
                        if tag in ["formula", "value"]:
                            matches = field_pattern.findall(node.text)
                            refs.extend(matches)
                        else:
                            refs.append(node.text)

            refs = list(set(refs))  # Deduplicate

            for field_name in refs:
                cur.execute("""
                    UPDATE SalesforceFlowFieldUsage
                    SET FlowStatus=?, LastSeen=?
                    WHERE FlowName=? AND FieldName=?
                """, (flow_status, now, flow_name, field_name))

                if cur.rowcount <= 0:
                    cur.execute("""
                        INSERT INTO SalesforceFlowFieldUsage
                        (FlowName, FlowStatus, FieldName, LastSeen)
                        VALUES (?, ?, ?, ?)
                    """, (flow_name, flow_status, field_name, now))
        except Exception as e:
            print(f"⚠️ Failed to parse {file}: {e}")

    if not keep_flow_xml:
        shutil.rmtree(flow_dir, ignore_errors=True)
        if not os.listdir(os.path.dirname(flow_dir)):
            shutil.rmtree(os.path.dirname(flow_dir), ignore_errors=True)

def report_flows():
    cur.execute("""
        SELECT FlowName, FlowStatus, FieldName
        FROM SalesforceFlowFieldUsage
        ORDER BY FlowName, FieldName
    """)
    rows = cur.fetchall()
    if not rows:
        print("⚠️ No flow field usage data found. Run a sync first.")
        return

    print("🔹 Fields used in Flows:")
    current_flow = None
    for flow_name, flow_status, field_name in rows:
        if flow_name != current_flow:
            print(f"Flow: {flow_name} ({flow_status})")
            current_flow = flow_name
        print(f"   - {field_name}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--report" and len(sys.argv) > 2 and sys.argv[2] == "flows":
        report_flows()
        return

    sync_flow_field_usage()
    print("✅ Flow field usage sync complete")    

if __name__ == "__main__":
    main()
