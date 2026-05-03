import sqlite3

def check_schema():
    try:
        conn = sqlite3.connect('giftcode.sqlite')
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='giftcodecontrol'")
        if not cursor.fetchone():
            print("Table 'giftcodecontrol' does not exist.")
            return

        # Get table info
        cursor.execute("PRAGMA table_info(giftcodecontrol)")
        columns = cursor.fetchall()
        print("Columns in giftcodecontrol:")
        for col in columns:
            print(col)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_schema()
