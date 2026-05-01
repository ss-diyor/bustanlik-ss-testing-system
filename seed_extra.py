import os
# Set dummy env vars for config.py to load without error
os.environ["BOT_TOKEN"] = "dummy_token"
os.environ["ADMIN_IDS"] = "1746229472"

import psycopg2
from database import get_connection, release_connection
from datetime import datetime, timedelta

def seed_data():
    conn = get_connection()
    cur = conn.cursor()
    
    # Materiallar
    materials = [
        ('Matematika formulalar to\'plami', 'pdf', 'https://example.com/math.pdf', 'Matematika', 'Barchaga'),
        ('Fizika: Mexanika bo\'limi', 'pdf', 'https://example.com/physics.pdf', 'Fizika', '11-A'),
        ('Ingliz tili: Grammatika sirlari', 'pdf', 'https://example.com/english.pdf', 'Ingliz tili', 'Barchaga'),
        ('Kimyo: Organik birikmalar', 'video', 'https://youtube.com/example', 'Kimyo', '10-B')
    ]
    
    for m in materials:
        cur.execute(
            "INSERT INTO materiallar (nomi, turi, link, fanni_nomi, sinf) VALUES (%s, %s, %s, %s, %s)",
            m
        )
        
    # Taqvim
    today = datetime.now().date()
    schedule = [
        ('Choraklik nazorat ishi', today + timedelta(days=2), '09:00', 'Barchaga'),
        ('Matematika olimpiadasi', today + timedelta(days=5), '14:00', '11-A'),
        ('Ingliz tili speaking test', today + timedelta(days=7), '10:30', '10-B')
    ]
    
    for s in schedule:
        cur.execute(
            "INSERT INTO test_taqvimi (test_nomi, sana, vaqt, sinf) VALUES (%s, %s, %s, %s)",
            s
        )
        
    conn.commit()
    cur.close()
    release_connection(conn)
    print("Seed data added successfully!")

if __name__ == "__main__":
    seed_data()
