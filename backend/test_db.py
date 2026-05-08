import os
import psycopg2
from dotenv import load_dotenv

def test_db_connection():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found in environment.")
        return

    print(f"Testing Database connection to: {db_url.split('@')[1] if '@' in db_url else 'unknown'}")
    
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"Successfully connected to the database!")
        print(f"Database version: {version[0]}")
        
        # Check current tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cur.fetchall()
        print(f"Tables in 'public' schema: {[t[0] for t in tables]}")
        
        cur.close()
        conn.close()
        print("Success: Database connection is working.")
    except Exception as e:
        print(f"Error connecting to the database: {e}")

if __name__ == "__main__":
    test_db_connection()
