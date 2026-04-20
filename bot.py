import os
import asyncio
import random
from datetime import datetime
import anthropic
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# ============================
# НАЛАШТУВАННЯ — заповни тут!
# ============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ВАШ_ТОКЕН_ВІД_BOTFATHER")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "ВАШ_ANTHROPIC_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@VartaFinance")  # або числовий ID каналу

# Розклад: пн=0, вт=1, ср=2, чт=3, пт=4, сб=5, нд=6
# Поточний: пн, ср, пт о 10:00 Київ
SCHEDULE_DAYS = "0,2,4"
SCHEDULE_HOUR = 10
SCHEDULE_MINUTE = 0
TIMEZONE = "Europe/Kiev"
# ============================

SYSTEM_PROMPT = """Ти — контент-менеджер для Telegram-каналу @VartaFinance фінансового консультанта Оксани з Одеси (Україна). 
Вона спеціалізується на страхуванні та пенсійному плануванні, працює зі страховою компанією GRAWE Ukraine.

ПРАВИЛА ПОСТІВ:
- Мова: виключно українська, без суржику
- Тон: дружній і теплий, як порада від близької людини
- Довжина: 150-280 слів (оптимально для Telegram)
- Обов'язково згадувати реальні норми законодавства України (назва закону, номер статті або номер закону)
- Не писати загальні фрази — тільки конкретика
- Закінчення: або запитання до читачів, або м'який CTA (написати в особисті / записатись на консультацію)
- Використовувати емодзі органічно (3-6 на пост), не спамити ними
- НЕ писати хештеги
- Підпис не потрібен"""

TOPICS = [
    {
        "name": "Пенсійне накопичення",
        "prompt": """Напиши освітній пост про пенсійне накопичення в Україні.
Теми: недержавні пенсійні фонди (НПФ), індивідуальні пенсійні рахунки, програми GRAWE Ukraine.
Законодавство: Закон № 1057-IV «Про недержавне пенсійне забезпечення», ст. 166.3.3 ПКУ (податкова знижка на внески до НПФ).
Акцент: середня пенсія в Україні ~3500-4000 грн — менше прожиткового мінімуму. Особисті накопичення — єдиний вихід.
Плавно підводь до думки що треба починати накопичувати самостійно."""
    },
    {
        "name": "Трудовий стаж",
        "prompt": """Напиши пост про трудовий стаж в Україні — що зараховується, як підтверджується.
Законодавство: КЗпП України, Закон № 1058-IV ст. 24-26 (страховий стаж), особливості для ФОП через ЄСВ.
Акцент: без мінімального страхового стажу (15 років) пенсія не призначається взагалі.
Корисна порада для самозайнятих, ФОП, моряків, IT-спеціалістів."""
    },
    {
        "name": "Солідарна пенсія",
        "prompt": """Напиши застережливий пост про солідарну (державну) пенсію в Україні.
Законодавство: Закон № 1058-IV, ст. 27 (умови призначення пенсії), бюджет ПФУ.
Факти: демографічна криза — на 10 пенсіонерів лише 6 платників ЄСВ. Система дефіцитна.
Реальна пенсія покриває ~30% від середньої зарплати.
Підводь до висновку: держава не встигне, треба дбати самому."""
    },
    {
        "name": "Е-трудова книжка",
        "prompt": """Напиши корисний пост про електронну трудову книжку (е-трудову) в Україні.
Законодавство: Закон № 1217-IX від 05.02.2021, постанова КМУ № 509 від 27.05.2021.
Як перевірити свій стаж в Дії або на сайті ПФУ.
Що робити якщо є помилки в записах — практична порада."""
    },
    {
        "name": "Страхування здоров'я",
        "prompt": """Напиши пост про добровільне медичне страхування (ДМС) в Україні.
Законодавство: Закон «Про страхування» № 85/96-ВР, ст. 142.1 ПКУ (пільги для роботодавців щодо ДМС).
Акцент: GRAWE Ukraine — австрійський капітал, понад 25 років на ринку, ліцензія НБУ.
В умовах воєнного стану доступ до якісної медицини — питання захисту сім'ї."""
    },
    {
        "name": "Страхування життя",
        "prompt": """Напиши пост про страхування життя в Україні як інструмент захисту і накопичення.
Законодавство: Закон «Про страхування» № 85/96-ВР, ст. 166.3.5 ПКУ (податкова знижка до 2690 грн/міс).
GRAWE Ukraine — поєднує захист + накопичення + податкову знижку.
Особливо актуально для ФОП, моряків, IT — у кого немає соціальних гарантій від держави."""
    },
    {
        "name": "Зміни КЗпП",
        "prompt": """Напиши інформаційний пост про зміни в трудовому законодавстві України.
Законодавство: КЗпП України, Закон № 2136-IX від 15.03.2022 (праця в умовах воєнного стану), Закон № 3720-IX.
Як зміни впливають на страховий стаж і майбутню пенсію.
Корисно знати кожному найманому працівнику і ФОП."""
    },
]

def get_next_topic(day_of_week: int) -> dict:
    """Обирає тему на основі дня тижня"""
    # пн=0: пенсія/страхування (освіта)
    # ср=2: стаж/законодавство (корисно)
    # пт=4: захист/GRAWE (м'який продаж)
    day_map = {0: [0, 4, 5], 2: [1, 2, 3], 4: [4, 5, 6]}
    topic_indices = day_map.get(day_of_week, list(range(len(TOPICS))))
    return random.choice([TOPICS[i] for i in topic_indices])


async def generate_post(topic: dict) -> str:
    """Генерує пост через Anthropic API"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": topic["prompt"]}
        ]
    )
    return message.content[0].text


async def publish_post():
    """Головна функція — генерує і публікує пост"""
    bot = Bot(token=TELEGRAM_TOKEN)
    
    kyiv_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(kyiv_tz)
    day_of_week = now.weekday()
    
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Генерую пост...")
    
    topic = get_next_topic(day_of_week)
    print(f"Тема: {topic['name']}")
    
    try:
        post_text = await generate_post(topic)
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=post_text,
            parse_mode=None
        )
        print(f"✅ Пост опубліковано! ({len(post_text)} символів)")
    except Exception as e:
        print(f"❌ Помилка: {e}")


async def main():
    print("🛡️ VartaFinance Bot запущено!")
    print(f"📣 Канал: {CHANNEL_ID}")
    print(f"🕐 Розклад: {SCHEDULE_DAYS} (пн/ср/пт) о {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} Київ")
    print("=" * 40)

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        publish_post,
        CronTrigger(
            day_of_week=SCHEDULE_DAYS,
            hour=SCHEDULE_HOUR,
            minute=SCHEDULE_MINUTE,
            timezone=TIMEZONE
        )
    )
    scheduler.start()

    # Тестовий запуск одразу при старті (можна закоментувати)
    print("⏳ Тестовий пост через 5 секунд...")
    await asyncio.sleep(5)
    await publish_post()

    print("\n✅ Бот працює. Чекаю на розклад...")
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Бот зупинено.")


if __name__ == "__main__":
    asyncio.run(main())
