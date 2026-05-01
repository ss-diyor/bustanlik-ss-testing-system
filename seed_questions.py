import os
# Set dummy env vars for config.py to load without error
os.environ["BOT_TOKEN"] = "dummy_token"
os.environ["ADMIN_IDS"] = "1746229472"

import json
from database import get_connection, release_connection

def seed_questions():
    conn = get_connection()
    cur = conn.cursor()
    
    questions = [
        ('Matematika', '2 + 2 * 2 necha bo\'ladi?', ['4', '6', '8', '0'], 1, 'Amallar tartibiga ko\'ra avval ko\'paytirish bajariladi.'),
        ('Matematika', 'Uchburchakning ichki burchaklari yig\'indisi necha gradus?', ['90', '180', '270', '360'], 1, 'Barcha yassi uchburchaklar uchun bu 180 gradus.'),
        ('Tarix', 'Amir Temur nechanchi yilda tug\'ilgan?', ['1336', '1342', '1405', '1370'], 0, 'Sohibqiron Amir Temur 1336-yil 9-aprelda tug\'ilgan.'),
        ('Ona tili', 'O\'zbek tili nechanchi yilda davlat tili maqomini olgan?', ['1989', '1991', '1992', '1985'], 0, '1989-yil 21-oktabrda.'),
        ('Fizika', 'Yorug\'lik tezligi taxminan qancha?', ['300,000 km/s', '150,000 km/s', '1,000,000 km/s', '30,000 km/s'], 0, 'Vakuumda yorug\'lik tezligi ~300,000 km/s.')
    ]
    
    for q in questions:
        cur.execute(
            "INSERT INTO practice_questions (subject, question, options, correct_option, explanation) VALUES (%s, %s, %s, %s, %s)",
            (q[0], q[1], json.dumps(q[2]), q[3], q[4])
        )
        
    conn.commit()
    cur.close()
    release_connection(conn)
    print("Practice questions seeded successfully!")

if __name__ == "__main__":
    seed_questions()
