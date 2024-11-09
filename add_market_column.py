import sqlite3

DATABASE = 'trades.db'


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


with get_db() as conn:
    try:
        # Schritt 1: Spalte hinzufügen ohne NOT NULL
        conn.execute('ALTER TABLE trades ADD COLUMN market TEXT')
        print("Column 'market' added successfully.")



    except sqlite3.OperationalError as e:
        print("Error:", e)
