import os
import asyncio
import random
from datetime import datetime
import anthropic
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@VartaFinance")
SCHEDULE_DAYS = "0,2,4"
SCHEDULE_HOUR = 10
SCHEDULE_MINUTE = 0
TIMEZONE = "Europe/Kiev"

SYSTEM_PROMPT = "Napyshi post ukrayinskoyu movoyu dlya Telegram kanalu pro finansy ta strakhuvannya v Ukrayini. Ton druzhniy. Zgaduy zakony. Dovzhyna 150-280 sliv. Emodzhi 3-6. Bez kheshteyhiv."

TOPICS = [
    {"name": "pension", "day": [0], "text": "Napyshi post pro pensiy ne nakopychennya. Zakon 1057-IV pro NPF. Stattya 166.3.3 PKU podatkova znyzhka. GRAWE Ukraine prohramy. Pensiya v Ukrayini 3500 hrn. Treba kopychyty samostiyno. Zaklyk na konsultatsiyu."},
    {"name": "stazh", "day": [2], "text": "Napyshi post pro trudovyy stazh. KZpP Ukrayiny. Zakon 1058-IV statti 24-26 strakhovyy stazh. Bez 15 rokiv stazhu pensiya ne pryznachayetsya. Porada dlya FOP moryakiv IT."},
    {"name": "solidarna", "day": [2], "text": "Napyshi post pro derzhavnu pensiyu. Zakon 1058-IV stattya 27. Na 10 pensivoneriv 6 platnykiv. Pensiya 30 vidsotky zarplaty. Treba kopychyty samostiyno."},
    {"name": "etrudova", "day": [2], "text": "Napyshi post pro elektronnu trudovu knyzhku. Zakon 1217-IX 2021 roku. Postanova KMU 509. Yak pereviryt stazh v Diyi. Shcho robyty pry pomylkakh."},
    {"name": "dms", "day": [4], "text": "Napyshi post pro DMS medychne strakhuvannya. Zakon 85/96-VR. Stattya 142.1 PKU. GRAWE Ukraine 25 rokiv na rynku litsenziya NBU. Zakhyst simyi pid chas viyiny."},
    {"name": "life", "day": [4], "text": "Napyshi post pro strakhuvannya zhyttya. Zakon 85/96-VR. Stattya 166.3.5 PKU znyzhka 2690 hrn. GRAWE zakhyst nakopychennya znyzhka. Dlya FOP moryakiv IT. Zaklyk na konsultatsiyu."},
    {"name": "kzpp", "day": [0], "text": "Napyshi post pro zminy KZpP. Zakon 2136-IX 2022. Zakon 3720-IX. Vplyv na stazh i pensiyu. Dlya naymanykh ta FOP."},
]

def get_topic(day_of_week):
    matching = [t for t in TOPICS if day_of_week in t["day"]]
    if not matching:
        matching = TOPICS
    return random.choice(matching)

async def generate_post(topic):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": topic["text"]}]
    )
    return msg.content[0].text

async def publish_post():
    bot = Bot(token=TELEGRAM_TOKEN)
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    topic = get_topic(now.weekday())
    print("Topic: " + topic["name"])
    try:
        text = await generate_post(topic)
        await bot.send_message(chat_id=CHANNEL_ID, text=text)
        print("Posted OK chars: " + str(len(text)))
    except Exception as e:
        print("Error: " + repr(e))

async def main():
    print("VartaFinance Bot started!")
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(publish_post, CronTrigger(day_of_week=SCHEDULE_DAYS, hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone=TIMEZONE))
    scheduler.start()
    print("Test post in 5 sec...")
    await asyncio.sleep(5)
    await publish_post()
    print("Running...")
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
