# -*- coding: utf-8 -*-
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
# НАЛАШТУВАННЯ
# ============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@VartaFinance")
SCHEDULE_DAYS = "0,2,4"
SCHEDULE_HOUR = 10
SCHEDULE_MINUTE = 0
TIMEZONE = "Europe/Kiev"
# ============================
SYSTEM_PROMPT = """Ти — контент-менеджер для Telegram-каналу @VartaFinance фінансового консул
Вона спеціалізується на страхуванні та пенсійному плануванні, працює зі страховою компанією G
ПРАВИЛА ПОСТІВ:
- Мова: виключно українська, без суржику
- Тон: дружній і теплий, як порада від близької людини
- Довжина: 150-280 слів (оптимально для Telegram)
- Обов'язково згадувати реальні норми законодавства України (назва закону, номер статті або н
- Не писати загальні фрази — тільки конкретика
- Закінчення: або запитання до читачів, або м'який CTA (написати в особисті / записатись на к
- Використовувати емодзі органічно (3-6 на пост), не спамити ними
- НЕ писати хештеги
- Підпис не потрібен"""
TOPICS = [
{
"name": "pension_accumulation",
"prompt": """Напиши освітній пост про пенсійне накопичення в Україні.
Теми: недержавні пенсійні фонди (НПФ), індивідуальні пенсійні рахунки, програми GRAWE Ukraine
Законодавство: Закон N 1057-IV "Про недержавне пенсійне забезпечення", ст. 166.3.3 ПКУ (подат
Акцент: середня пенсія в Україні 3500-4000 грн — менше прожиткового мінімуму. Особисті Плавно підводь до думки що треба починати накопичувати самостійно."""
накопи
},
{
"name": "work_experience",
"prompt": """Напиши пост про трудовий стаж в Україні — що зараховується, як підтвердж
Законодавство: КЗпП України, Закон N 1058-IV ст. 24-26 (страховий стаж), особливості для ФОП
Акцент: без мінімального страхового стажу (15 років) пенсія не призначається взагалі.
Корисна порада для самозайнятих, ФОП, моряків, IT-спеціалістів."""
},
{
"name": "solidarity_pension",
"prompt": """Напиши застережливий пост про солідарну (державну) пенсію в Україні.
Законодавство: Закон N 1058-IV, ст. 27 (умови призначення пенсії), бюджет ПФУ.
Факти: демографічна криза — на 10 пенсіонерів лише 6 платників ЄСВ. Система дефіцитна.
Реальна пенсія покриває близько 30% від середньої зарплати.
Підводь до висновку: держава не встигне, треба дбати самому."""
},
{
"name": "digital_work_book",
"prompt": """Напиши корисний пост про електронну трудову книжку (е-трудову) в Україні
Законодавство: Закон N 1217-IX від 05.02.2021, постанова КМУ N 509 від 27.05.2021.
Як перевірити свій стаж в Дії або на сайті ПФУ.
Що робити якщо є помилки в записах — практична порада."""
},
{
"name": "health_insurance",
"prompt": """Напиши пост про добровільне медичне страхування (ДМС) в Україні.
Законодавство: Закон "Про страхування" N 85/96-ВР, ст. 142.1 ПКУ (пільги для роботодавців щод
Акцент: GRAWE Ukraine — австрійський капітал, понад 25 років на ринку, ліцензія НБУ.
В умовах воєнного стану доступ до якісної медицини — питання захисту сім'ї."""
},
{
"name": "life_insurance",
"prompt": """Напиши пост про страхування життя в Україні як інструмент захисту і нако
Законодавство: Закон "Про страхування" N 85/96-ВР, ст. 166.3.5 ПКУ (податкова знижка до 2690
GRAWE Ukraine — поєднує захист + накопичення + податкову знижку.
Особливо актуально для ФОП, моряків, IT — у кого немає соціальних гарантій від держави."""
},
{
"name": "labor_code_changes",
"prompt": """Напиши інформаційний пост про зміни в трудовому законодавстві України.
Законодавство: КЗпП України, Закон N 2136-IX від 15.03.2022 (праця в умовах воєнного стану),
Як зміни впливають на страховий стаж і майбутню пенсію.
Корисно знати кожному найманому працівнику і ФОП."""
},
]
def get_next_topic(day_of_week: int) -> dict:
day_map = {0: [0, 4, 5], 2: [1, 2, 3], 4: [4, 5, 6]}
topic_indices = day_map.get(day_of_week, list(range(len(TOPICS))))
return random.choice([TOPICS[i] for i in topic_indices])
async def generate_post(topic: dict) -> str:
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
message = client.messages.create(
model="claude-opus-4-5",
max_tokens=1000,
system=SYSTEM_PROMPT,
messages=[{"role": "user", "content": topic["prompt"]}]
)
return message.content[0].text
async def publish_post():
bot = Bot(token=TELEGRAM_TOKEN)
kyiv_tz = pytz.timezone(TIMEZONE)
now = datetime.now(kyiv_tz)
day_of_week = now.weekday()
print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Generating post...")
topic = get_next_topic(day_of_week)
print(f"Topic: {topic['name']}")
try:
post_text = await generate_post(topic)
await bot.send_message(
chat_id=CHANNEL_ID,
text=post_text,
parse_mode=None
)
print(f"OK! Post published! {len(post_text)} chars")
except Exception as e:
print(f"ERROR: {repr(e)}")
async def main():
print("VartaFinance Bot started!")
print(f"Channel: {CHANNEL_ID}")
print(f"Schedule: days {SCHEDULE_DAYS} at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} Kyiv"
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
print("Test post in 5 seconds...")
await asyncio.sleep(5)
await publish_post()
print("Bot running. Waiting for schedule...")
try:
while True:
await asyncio.sleep(60)
except (KeyboardInterrupt, SystemExit):
scheduler.shutdown()
print("Bot stopped.")
if __name__ == "__main__":
asyncio.run(main())
