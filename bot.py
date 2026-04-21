import os
import asyncio
import random
from datetime import datetime
import anthropic
import openai
from telegram import Bot, Poll
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@VartaFinance")

SCHEDULE_DAYS = "0,2,4"
SCHEDULE_HOUR = 10
SCHEDULE_MINUTE = 0
TIMEZONE = "Europe/Kiev"

SYSTEM_PROMPT = "Napyshi post ukrayinskoyu movoyu dlya Telegram kanalu pro finansy ta strakhuvannya v Ukrayini. Ton druzhniy. Zgaduy zakony. Dovzhyna 150-280 sliv. Emodzhi 3-6. Bez kheshteyhiv."

TOPICS = [
    {
        "name": "pension",
        "day": [0],
        "text": "Napyshi post pro pensiy ne nakopychennya. Zakon 1057-IV pro NPF. Stattya 166.3.3 PKU podatkova znyzhka. GRAWE Ukraine prohramy. Pensiya v Ukrayini 3500 hrn. Treba kopychyty samostiyno. Zaklyk na konsultatsiyu.",
        "image_prompt": "Ukrainian financial planning, pension savings, coins and calendar, warm colors, professional illustration, no text",
        "poll_question": "Chy dumaly vy pro pensiyni nakopychennya?",
        "poll_options": ["Tak, vzhe nakopychuyu", "Dumav ale ne pochav", "Shche ni, але плануюю", "Pensiya? Sche daleko"]
    },
    {
        "name": "stazh",
        "day": [2],
        "text": "Napyshi post pro trudovyy stazh. KZpP Ukrayiny. Zakon 1058-IV statti 24-26 strakhovyy stazh. Bez 15 rokiv stazhu pensiya ne pryznachayetsya. Porada dlya FOP moryakiv IT.",
        "image_prompt": "Work experience document, Ukrainian labor book, professional career timeline, blue and gold colors, clean illustration, no text",
        "poll_question": "Chy znayete skilky rokiv stazhu u vas zaraz?",
        "poll_options": ["Tak, znayu tochno", "Pryblyzhno znayu", "Ne znayu", "Budu pereviryaty"]
    },
    {
        "name": "solidarna",
        "day": [2],
        "text": "Napyshi post pro derzhavnu pensiyu. Zakon 1058-IV stattya 27. Na 10 pensivoneriv 6 platnykiv. Pensiya 30 vidsotky zarplaty. Treba kopychyty samostiyno.",
        "image_prompt": "Ukrainian pension fund concept, elderly people and young workers balance scale, financial security, soft colors, professional illustration, no text",
        "poll_question": "Na yaku pensiyu vy rozrakhovuyete?",
        "poll_options": ["Tilky derzhavna", "Derzhavna plus NPF", "Tilky vlasni zaoschadzhennya", "Shche ne dumav"]
    },
    {
        "name": "etrudova",
        "day": [2],
        "text": "Napyshi post pro elektronnu trudovu knyzhku. Zakon 1217-IX 2021 roku. Postanova KMU 509. Yak pereviryt stazh v Diyi. Shcho robyty pry pomylkakh.",
        "image_prompt": "Digital document on smartphone screen, Diia app Ukraine concept, modern technology and documents, blue colors, clean illustration, no text",
        "poll_question": "Chy pereviraly vy sviy stazh v Diyi?",
        "poll_options": ["Tak, vse harazd", "Pereviryav, znayshov pomylky", "Shche ni, pidu pereviryu", "Ne znayu yak"]
    },
    {
        "name": "dms",
        "day": [4],
        "text": "Napyshi post pro DMS medychne strakhuvannya. Zakon 85/96-VR. Stattya 142.1 PKU. GRAWE Ukraine 25 rokiv na rynku litsenziya NBU. Zakhyst simyi pid chas viyiny.",
        "image_prompt": "Health insurance concept, medical care and family protection, shield and heart symbol, green and white colors, professional illustration, no text",
        "poll_question": "Chy maye vasha simya DMS?",
        "poll_options": ["Tak, maye", "Tilky ya mayu", "Ni, ale khochu oformyty", "Ni, ne planuyu"]
    },
    {
        "name": "life",
        "day": [4],
        "text": "Napyshi post pro strakhuvannya zhyttya. Zakon 85/96-VR. Stattya 166.3.5 PKU znyzhka 2690 hrn. GRAWE zakhyst nakopychennya znyzhka. Dlya FOP moryakiv IT. Zaklyk na konsultatsiyu.",
        "image_prompt": "Life insurance concept, family protection umbrella, GRAWE insurance company style, trust and security, warm professional illustration, no text",
        "poll_question": "Chy ye u vas strakhuvannya zhyttya?",
        "poll_options": ["Tak, vzhe oformyv", "Rozglyadam variant", "Shche ni, tsikavo diznatys", "Ni, ne potribno"]
    },
    {
        "name": "kzpp",
        "day": [0],
        "text": "Napyshi post pro zminy KZpP. Zakon 2136-IX 2022. Zakon 3720-IX. Vplyv na stazh i pensiyu. Dlya naymanykh ta FOP.",
        "image_prompt": "Ukrainian labor law book, legal documents and scales of justice, professional business concept, blue and gold colors, clean illustration, no text",
        "poll_question": "Chy slidkuyete za zminamy trudovoho zakonodavstva?",
        "poll_options": ["Tak, postiyn", "Inodi chytayu novyny", "Ni, ne vstygayu", "Meni rozpoviv konsultant"]
    },
]

# Чергування: парні пости - картинка, непарні - опитування
post_counter_file = "/tmp/post_counter.txt"

def get_post_counter():
    try:
        with open(post_counter_file, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def increment_counter():
    count = get_post_counter() + 1
    with open(post_counter_file, "w") as f:
        f.write(str(count))
    return count

def get_topic(day_of_week):
    matching = [t for t in TOPICS if day_of_week in t["day"]]
    if not matching:
        matching = TOPICS
    return random.choice(matching)

async def generate_text(topic):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": topic["text"]}]
    )
    return msg.content[0].text

async def generate_image(prompt):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url

async def publish_post():
    bot = Bot(token=TELEGRAM_TOKEN)
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    topic = get_topic(now.weekday())
    counter = get_post_counter()
    use_image = (counter % 2 == 0)
    increment_counter()

    print("Topic: " + topic["name"] + " | Type: " + ("image" if use_image else "poll"))

    try:
        text = await generate_text(topic)

        if use_image:
            print("Generating image...")
            image_url = await generate_image(topic["image_prompt"])
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_url,
                caption=text
            )
            print("Posted with image OK")
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=text)
            await bot.send_poll(
                chat_id=CHANNEL_ID,
                question=topic["poll_question"],
                options=topic["poll_options"],
                is_anonymous=True
            )
            print("Posted with poll OK")

    except Exception as e:
        print("Error: " + repr(e))

async def main():
    print("VartaFinance Bot started with images and polls!")
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
