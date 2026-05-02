from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_connection, release_connection
import json
import random

router = Router()

class PracticeState(StatesGroup):
    selecting_subject = State()
    answering = State()

@router.message(F.text == "📝 Mashq qilish (Quiz)")
async def start_practice(message: Message, state: FSMContext):
    """Mashq qilishni boshlash — fan tanlash."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT subject FROM practice_questions")
    subjects = [r[0] for r in cur.fetchall()]
    cur.close()
    release_connection(conn)
    
    if not subjects:
        await message.answer("😔 Hozircha mashq qilish uchun savollar yuklanmagan.")
        return
        
    for s in subjects:
        keyboard.append([InlineKeyboardButton(text=s, callback_data=f"quiz_start:{s}")])
    
    # Corrected keyboard construction
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=s, callback_data=f"quiz_start:{s}")] for s in subjects
    ])
    
    await message.answer("📚 Qaysi fandan mashq qilmoqchisiz?", reply_markup=kb)
    await state.set_state(PracticeState.selecting_subject)

@router.callback_query(F.data.startswith("quiz_start:"))
async def quiz_start_subject(callback: CallbackQuery, state: FSMContext):
    subject = callback.data.split(":")[1]
    await state.update_data(subject=subject, score=0, count=0, answered_ids=[])
    await callback.answer()
    await send_next_question(callback.message, state)

async def send_next_question(message: Message, state: FSMContext):
    data = await state.get_data()
    subject = data['subject']
    answered_ids = data['answered_ids']
    
    conn = get_connection()
    import psycopg2.extras
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    if answered_ids:
        cur.execute("SELECT * FROM practice_questions WHERE subject=%s AND id NOT IN %s ORDER BY RANDOM() LIMIT 1", (subject, tuple(answered_ids)))
    else:
        cur.execute("SELECT * FROM practice_questions WHERE subject=%s ORDER BY RANDOM() LIMIT 1", (subject,))
        
    question = cur.fetchone()
    cur.close()
    release_connection(conn)
    
    if not question:
        score = data['score']
        count = data['count']
        await message.edit_text(f"🏁 <b>Mashq yakunlandi!</b>\n\nNatija: <b>{score}/{count}</b>\n\nYana mashq qilishingiz mumkin!", parse_mode="HTML")
        await state.clear()
        return
        
    options = question['options']
    if isinstance(options, str): options = json.loads(options)
    
    kb_list = []
    for i, opt in enumerate(options):
        kb_list.append([InlineKeyboardButton(text=opt, callback_data=f"quiz_ans:{question['id']}:{i}")])
    
    kb_list.append([InlineKeyboardButton(text="❌ Yakunlash", callback_data="quiz_stop")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    
    await message.edit_text(f"❓ <b>Savol:</b>\n\n{question['question']}", reply_markup=kb, parse_mode="HTML")
    await state.set_state(PracticeState.answering)

@router.callback_query(F.data.startswith("quiz_ans:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    _, q_id, ans_idx = callback.data.split(":")
    ans_idx = int(ans_idx)
    
    conn = get_connection()
    import psycopg2.extras
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM practice_questions WHERE id=%s", (q_id,))
    question = cur.fetchone()
    cur.close()
    release_connection(conn)
    
    if not question:
        await callback.answer("Xatolik: Savol topilmadi")
        return

    data = await state.get_data()
    correct = (ans_idx == question['correct_option'])
    new_score = data['score'] + (1 if correct else 0)
    new_count = data['count'] + 1
    new_answered = data['answered_ids'] + [int(q_id)]
    
    await state.update_data(score=new_score, count=new_count, answered_ids=new_answered)
    
    options = question['options']
    if isinstance(options, str): options = json.loads(options)
    correct_text = options[question['correct_option']]
    
    if correct:
        res_text = "✅ <b>To'g'ri!</b>"
    else:
        res_text = f"❌ <b>Noto'g'ri.</b>\nTo'g'ri javob: <b>{correct_text}</b>"
        
    if question['explanation']:
        res_text += f"\n\n💡 <i>Izoh: {question['explanation']}</i>"
        
    await callback.answer("Keyingi savol yuklanmoqda...")
    await callback.message.answer(res_text, parse_mode="HTML")
    await send_next_question(callback.message, state)

@router.callback_query(F.data == "quiz_stop")
async def stop_quiz(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get('score', 0)
    count = data.get('count', 0)
    await callback.message.edit_text(f"🏁 <b>Mashq to'xtatildi.</b>\n\nNatija: <b>{score}/{count}</b>", parse_mode="HTML")
    await state.clear()
    await callback.answer()
