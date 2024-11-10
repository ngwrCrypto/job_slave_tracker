import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, date, timedelta
from sqlalchemy import extract
from models import Session, WorkDay
from config import BOT_TOKEN
from language import TRANSLATIONS

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_chat_id = None
user_language = {}  # save language for each user

TRANSLATIONS = TRANSLATIONS

def get_keyboard(lang='uk'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TRANSLATIONS[lang]['yes'], callback_data="yes"),
             InlineKeyboardButton(text=TRANSLATIONS[lang]['no'], callback_data="no")],
            [InlineKeyboardButton(text=TRANSLATIONS[lang]['show_results'], callback_data="results")],
            [InlineKeyboardButton(text=TRANSLATIONS[lang]['select_days'], callback_data="select_days")]
        ]
    )

def get_language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_uk"),
             InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
        ]
    )

def create_calendar_keyboard(year: int, month: int, lang='uk'):
    keyboard = []

    month_names_uk = ['Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень',
                     'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень']
    month_names_en = ['January', 'February', 'March', 'April', 'May', 'June',
                     'July', 'August', 'September', 'October', 'November', 'December']

    month_names = month_names_uk if lang == 'uk' else month_names_en

    header = [InlineKeyboardButton(
        text=f"{month_names[month-1]} {year}",
        callback_data="ignore"
    )]
    keyboard.append(header)

    days_of_week_uk = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
    days_of_week_en = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
    days_of_week = days_of_week_uk if lang == 'uk' else days_of_week_en

    week_header = [InlineKeyboardButton(text=day, callback_data="ignore") for day in days_of_week]
    keyboard.append(week_header)

    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    current_week = []
    weekday = first_day.weekday()

    for _ in range(weekday):
        current_week.append(InlineKeyboardButton(text=" ", callback_data="ignore"))

    for day in range(1, last_day.day + 1):
        current_date = date(year, month, day)
        current_week.append(InlineKeyboardButton(
            text=str(day),
            callback_data=f"calendar_{current_date.strftime('%Y-%m-%d')}"
        ))

        if len(current_week) == 7:
            keyboard.append(current_week)
            current_week = []

    if current_week:
        while len(current_week) < 7:
            current_week.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
        keyboard.append(current_week)

    nav_row = []
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    nav_row.append(InlineKeyboardButton(
        text="<<",
        callback_data=f"nav_{prev_year}_{prev_month}"
    ))
    nav_row.append(InlineKeyboardButton(
        text=">>",
        callback_data=f"nav_{next_year}_{next_month}"
    ))
    keyboard.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global user_chat_id
    user_chat_id = message.chat.id
    await message.answer(
        TRANSLATIONS['uk']['select_language'],
        reply_markup=get_language_keyboard()
    )

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    user_lang = user_language.get(callback.from_user.id, 'uk')

    if callback.data.startswith('lang_'):
        selected_lang = callback.data.split('_')[1]
        user_language[callback.from_user.id] = selected_lang
        await callback.message.answer(
            TRANSLATIONS[selected_lang]['greeting'],
            reply_markup=get_keyboard(selected_lang)
        )
        await callback.answer()
        return

    if callback.data == "select_days":
        now = datetime.now()
        calendar_keyboard = create_calendar_keyboard(now.year, now.month, user_lang)
        await callback.message.answer(TRANSLATIONS[user_lang]['select_date'], reply_markup=calendar_keyboard)
        await callback.answer()
        return

    if callback.data.startswith("nav_"):
        _, year, month = callback.data.split("_")
        calendar_keyboard = create_calendar_keyboard(int(year), int(month), user_lang)
        await callback.message.edit_reply_markup(reply_markup=calendar_keyboard)
        await callback.answer()
        return

    if callback.data == "ignore":
        await callback.answer()
        return

    if callback.data == "results":
        with Session() as session:
            current_month = datetime.now().month
            current_year = datetime.now().year

            work_days = session.query(WorkDay).filter(
                extract('year', WorkDay.date) == current_year,
                extract('month', WorkDay.date) == current_month,
                WorkDay.worked == True
            ).count()

            await callback.message.answer(TRANSLATIONS[user_lang]['worked_days'].format(work_days))
            await callback.answer()
            return

    if callback.data.startswith('calendar_'):
        selected_date = datetime.strptime(callback.data.split('_')[1], '%Y-%m-%d').date()

        with Session() as session:
            work_day = session.query(WorkDay).filter(WorkDay.date == selected_date).first()
            if not work_day:
                work_day = WorkDay(date=selected_date, worked=True)
                session.add(work_day)
            else:
                work_day.worked = True
            session.commit()

        await callback.message.answer(TRANSLATIONS[user_lang]['marked_day'].format(selected_date))
        await callback.answer()
        return

    if callback.data not in ["yes", "no"]:
        await callback.answer()
        return

    worked = callback.data == "yes"
    today = date.today()

    with Session() as session:
        work_day = session.query(WorkDay).filter(WorkDay.date == today).first()
        if not work_day:
            work_day = WorkDay(date=today, worked=worked)
            session.add(work_day)
        else:
            work_day.worked = worked
        session.commit()

    response = TRANSLATIONS[user_lang]['worked_response'] if worked else TRANSLATIONS[user_lang]['not_worked_response']
    await callback.message.answer(response)
    await callback.answer()

async def ask_daily():
    while True:
        now = datetime.now()
        if now.hour == 9 and now.minute == 0 and user_chat_id:
            for user_id, lang in user_language.items():
                await bot.send_message(
                    chat_id=user_id,
                    text=TRANSLATIONS[lang]['good_morning'],
                    reply_markup=get_keyboard(lang)
                )

        if now.day == 1 and now.hour == 9 and now.minute == 0 and user_chat_id:
            with Session() as session:
                last_month = now.month - 1 if now.month > 1 else 12
                last_month_year = now.year if now.month > 1 else now.year - 1

                work_days = session.query(WorkDay).filter(
                    extract('year', WorkDay.date) == last_month_year,
                    extract('month', WorkDay.date) == last_month,
                    WorkDay.worked == True
                ).count()

                for user_id, lang in user_language.items():
                    await bot.send_message(
                        chat_id=user_id,
                        text=TRANSLATIONS[lang]['monthly_report'].format(work_days)
                    )

        await asyncio.sleep(60)

async def main():
    asyncio.create_task(ask_daily())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
