from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import mini_test_ol, mini_test_natija_saqlash, get_connection, release_connection
import asyncio

router = Router()

class MiniTestProcess(StatesGroup):
    answering = State()

@router.callback_query(F.data.startswith("minitest_start:"))
async def start_mini_test(callback: CallbackQuery, state: FSMContext):
    test_id = int(callback.data.split(":")[1])
    test = mini_test_ol(test_id)
    
    if not test:
        await callback.answer("❌ Test topilmadi.")
        return

    await state.update_data(test_id=test_id, answers={}, current_q=1)
    
    msg_text = f"🏁 <b>{test['nomi']}</b> boshlandi!\n\n"
    if test['pdf_file_id']:
        await callback.message.answer_document(test['pdf_file_id'], caption=msg_text + "Savollar PDF faylda. Javoblarni pastdagi tugmalar orqali yuboring.", parse_mode="HTML")
    else:
        await callback.message.answer(msg_text + "Javoblarni yuboring.", parse_mode="HTML")
        
    await send_answer_keyboard(callback.message, state, test)
    await callback.answer()

@router.message(F.text == "📦 Mini-testlar")
async def list_mini_tests(message: Message):
    from database import mini_test_hammasi
    tests = mini_test_hammasi()
    if not tests:
        await message.answer("😔 Hozircha faol mini-testlar yo'q.")
        return
        
    text = "📦 <b>Faol mini-testlar:</b>\n\n"
    buttons = []
    for t in tests:
        text += f"• {t['nomi']} ({t['fan']})\n"
        buttons.append([InlineKeyboardButton(text=t['nomi'], callback_data=f"minitest_start:{t['id']}")])
    
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

async def send_answer_keyboard(message: Message, state: FSMContext, test: dict):
    data = await state.get_data()
    q_num = data.get('current_q', 1)
    keys = test['keys']
    total = len(keys)
    
    if q_num > total:
        await finish_mini_test(message, state)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="A", callback_data=f"mt_ans:{q_num}:a"),
            InlineKeyboardButton(text="B", callback_data=f"mt_ans:{q_num}:b"),
            InlineKeyboardButton(text="C", callback_data=f"mt_ans:{q_num}:c"),
            InlineKeyboardButton(text="D", callback_data=f"mt_ans:{q_num}:d")
        ],
        [InlineKeyboardButton(text="🏁 Yakunlash", callback_data="mt_finish")]
    ])
    
    await message.answer(f"❓ <b>{q_num}-savol</b> javobini tanlang:", reply_markup=kb, parse_mode="HTML")
    await state.set_state(MiniTestProcess.answering)

@router.callback_query(F.data.startswith("mt_ans:"))
async def handle_mt_answer(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    q_num = int(parts[1])
    ans = parts[2]
    
    data = await state.get_data()
    answers = data.get('answers', {})
    answers[q_num] = ans
    
    await state.update_data(answers=answers, current_q=q_num + 1)
    
    # Eskisini tahrirlash (feedback)
    await callback.message.edit_text(f"✅ {q_num}-savol uchun <b>{ans.upper()}</b> tanlandi.", parse_mode="HTML")
    
    test = mini_test_ol(data['test_id'])
    await send_answer_keyboard(callback.message, state, test)
    await callback.answer()

@router.callback_query(F.data == "mt_finish")
async def manual_finish(callback: CallbackQuery, state: FSMContext):
    await finish_mini_test(callback.message, state)
    await callback.answer()

async def finish_mini_test(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get('test_id'): return
    
    test = mini_test_ol(data['test_id'])
    answers = data.get('answers', {})
    keys = test['keys'] 
    
    correct = 0
    total = len(keys)
    
    for q_num_str, correct_ans in keys.items():
        user_ans = answers.get(int(q_num_str))
        if user_ans == correct_ans:
            correct += 1
            
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT kod FROM talabalar WHERE user_id = %s", (message.chat.id,))
        row = cur.fetchone()
        kod = row[0] if row else None
        cur.close()
        release_connection(conn)
        
        mini_test_natija_saqlash(test['id'], message.chat.id, kod, float(correct), total)
    except Exception:
        if conn: release_connection(conn)

    res_text = (
        f"🏁 <b>Test yakunlandi!</b>\n\n"
        f"📝 Test: <b>{test['nomi']}</b>\n"
        f"✅ To'g'ri javoblar: <b>{correct} / {total}</b>\n"
        f"📊 Foiz: <b>{round(correct/total*100, 1)}%</b>"
    )
    
    await message.answer(res_text, parse_mode="HTML")
    await state.clear()
