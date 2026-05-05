

# =====================================================================
# GOOGLE SHEETS EKSPORT — handler bloki
# =====================================================================

class SheetsStudentKod(StatesGroup):
    kod_kutish = State()


@router.message(F.text == "📗 Google Sheets Eksport")
async def sheets_hisobot_start(message: Message, state: FSMContext):
    """Google Sheets Eksport — asosiy menyu."""
    if not await admin_tekshir(state, message.from_user.id):
        return
    await message.answer(
        "📗 <b>Google Sheets Eksport</b>\n\nQaysi ma'lumotni eksport qilmoqchisiz?",
        parse_mode="HTML",
        reply_markup=sheets_export_keyboard(),
    )


@router.callback_query(F.data.startswith("sheets:"))
async def sheets_export_callback(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id):
        return

    action = callback.data.split(":")[1]

    if action == "student":
        await state.set_state(SheetsStudentKod.kod_kutish)
        await callback.message.edit_text(
            "📗 Google Sheets ga yuklash uchun o'quvchi kodini kiriting:"
        )

    elif action == "all_students":
        wait_msg = await callback.message.answer("⏳ Google Sheets ga yuklanmoqda...")
        try:
            from sheets_export import export_all_students
            url = export_all_students()
            await wait_msg.delete()
            if url.startswith("❌"):
                await callback.message.answer(url)
            else:
                await callback.message.answer(
                    f"✅ <b>Barcha o'quvchilar Google Sheets ga yuklandi!</b>\n\n"
                    f"🔗 <a href='{url}'>Sheets ni ochish</a>",
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
        except Exception as e:
            await wait_msg.delete()
            await callback.message.answer(f"❌ Xatolik: {e}")

    elif action == "maktab_stat":
        from keyboards import maktab_tanlash_keyboard
        await callback.message.edit_text(
            "🏫 Maktab statistikasi uchun maktabni tanlang:",
            reply_markup=maktab_tanlash_keyboard(maktablar_ol(), "sheets_maktab"),
        )

    elif action == "sinf_reyting":
        from keyboards import sinf_tanlash_excel_keyboard as _sinf_kb
        # Sheets uchun alohida sinf callback ishlatamiz
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from database import sinf_ol as _sinf_ol
        sinflar = _sinf_ol()
        buttons = [
            [InlineKeyboardButton(text=s, callback_data=f"sheets_sinf:{s}")]
            for s in sinflar
        ]
        buttons.append(
            [InlineKeyboardButton(text="📋 Barcha sinflar", callback_data="sheets_sinf:all")]
        )
        buttons.append(
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="sheets:menu")]
        )
        await callback.message.edit_text(
            "🏆 Sinf reytingi uchun sinfni tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

    elif action == "menu":
        await callback.message.edit_text(
            "📗 <b>Google Sheets Eksport</b>\n\nQaysi ma'lumotni eksport qilmoqchisiz?",
            parse_mode="HTML",
            reply_markup=sheets_export_keyboard(),
        )

    await callback.answer()


@router.message(SheetsStudentKod.kod_kutish)
async def sheets_student_kod_handler(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id):
        return

    kod = message.text.strip().upper()
    from database import talaba_topish as _talaba_topish
    talaba = _talaba_topish(kod)

    if not talaba:
        await message.answer(
            f"❌ <code>{kod}</code> kodli o'quvchi topilmadi.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    wait_msg = await message.answer("⏳ Google Sheets ga yuklanmoqda...")
    try:
        from sheets_export import export_student_history
        url = export_student_history(kod)
        await wait_msg.delete()
        if url.startswith("❌"):
            await message.answer(url)
        else:
            await message.answer(
                f"✅ <b>{talaba['ismlar']}</b> tarixi Google Sheets ga yuklandi!\n\n"
                f"🔗 <a href='{url}'>Sheets ni ochish</a>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    except Exception as e:
        await wait_msg.delete()
        await message.answer(f"❌ Xatolik: {e}")

    await state.clear()


@router.callback_query(F.data.startswith("sheets_maktab:"))
async def sheets_maktab_callback(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id):
        return

    maktab_id = int(callback.data.split(":")[1])
    wait_msg = await callback.message.answer("⏳ Google Sheets ga yuklanmoqda...")
    try:
        from sheets_export import export_maktab_statistika
        url = export_maktab_statistika(maktab_id)
        await wait_msg.delete()
        if url.startswith("❌"):
            await callback.message.answer(url)
        else:
            await callback.message.answer(
                f"✅ <b>Maktab statistikasi</b> Google Sheets ga yuklandi!\n\n"
                f"🔗 <a href='{url}'>Sheets ni ochish</a>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        await callback.answer("✅ Yuklandi!", show_alert=False)
    except Exception as e:
        await wait_msg.delete()
        await callback.answer(f"❌ Xatolik: {e}", show_alert=True)


@router.callback_query(F.data.startswith("sheets_sinf:"))
async def sheets_sinf_callback(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id):
        return

    sinf = callback.data.split(":")[1]
    wait_msg = await callback.message.answer("⏳ Google Sheets ga yuklanmoqda...")
    try:
        from sheets_export import export_sinf_reyting
        url = export_sinf_reyting(sinf=sinf if sinf != "all" else None)
        await wait_msg.delete()
        if url.startswith("❌"):
            await callback.message.answer(url)
        else:
            await callback.message.answer(
                f"✅ <b>Sinf reytingi</b> Google Sheets ga yuklandi!\n\n"
                f"🔗 <a href='{url}'>Sheets ni ochish</a>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        await callback.answer("✅ Yuklandi!", show_alert=False)
    except Exception as e:
        await wait_msg.delete()
        await callback.answer(f"❌ Xatolik: {e}", show_alert=True)
