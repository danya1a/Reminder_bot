import sqlite3
from datetime import datetime

conn = sqlite3.connect("reminders.db", check_same_thread=False)
cursor = conn.cursor()

def create_table():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            time TEXT,
            tz TEXT
        )
    ''')
    conn.commit()

def add_reminder(user_id, text, time, tz):
    cursor.execute("INSERT INTO reminders (user_id, text, time, tz) VALUES (?, ?, ?, ?)",
                   (user_id, text, time.isoformat(), tz))
    conn.commit()
    return cursor.lastrowid

def get_reminders(user_id):
    conn = sqlite3.connect("reminders.db")
    c = conn.cursor()
    c.execute("SELECT * FROM reminders WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_reminder(reminder_id):
    conn = sqlite3.connect("reminders.db")
    c = conn.cursor()
    c.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()