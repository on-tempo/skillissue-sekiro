"""Delete expired records without opening the web server."""
import os, time
import db

def run(conn):
    cutoff = int(time.time()) - int(os.environ.get("RETENTION_DAYS", "90")) * 86400
    conn.execute("DELETE FROM submissions WHERE ts<?", (cutoff,))
    conn.commit()

if __name__ == '__main__':
    conn = db.connect()
    try:
        run(conn)
    finally:
        conn.close()
