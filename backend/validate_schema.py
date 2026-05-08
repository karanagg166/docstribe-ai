import os
import psycopg2
from dotenv import load_dotenv

def validate_schema():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Expected tables (placeholder for now)
        expected_tables = ["patients", "visit_history", "clinical_insights"]
        
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        existing_tables = [t[0] for t in cur.fetchall()]
        
        print(f"--- Database Schema Validation ---")
        print(f"Connection: SUCCESS")
        print(f"Existing Tables: {existing_tables if existing_tables else 'NONE'}")
        
        missing = [t for t in expected_tables if t not in existing_tables]
        if missing:
            print(f"Status: INCOMPLETE")
            print(f"Missing Expected Tables: {missing}")
            print(f"Action Required: Run migrations once implemented.")
        else:
            print(f"Status: VALID")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error validating schema: {e}")

if __name__ == "__main__":
    validate_schema()
