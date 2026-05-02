import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import urllib.request
import psycopg2

def load_northwind():
    print("Loading Northwind dataset for evaluation...")
    
    northwind_url = "https://raw.githubusercontent.com/pthom/northwind_psql/master/northwind.sql"
    sql_file = "/tmp/northwind.sql"
    
    if not os.path.exists(sql_file):
        print(f"Downloading Northwind from {northwind_url}...")
        urllib.request.urlretrieve(northwind_url, sql_file)
        print("Download complete.")
    else:
        print("Northwind SQL already downloaded.")

    from src.config.settings import settings
    url = settings.database_url.replace("+asyncpg", "")
    print(f"Connecting to {url}...")
    
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cur = conn.cursor()

        print("Resetting schema...")
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")

        print(f"Loading {sql_file}...")
        with open(sql_file, "r") as f:
            sql = f.read()
        cur.execute(sql)

        cur.close()
        conn.close()
        print("✅ Northwind database loaded successfully.")
    except Exception as e:
        print(f"❌ Failed to load Northwind: {e}")


if __name__ == "__main__":
    load_northwind()