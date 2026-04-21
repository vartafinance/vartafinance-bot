import os
import asyncio
import random
import io
from datetime import datetime
import anthropic
import openai
import requests
from PIL import Image, ImageDraw, ImageFont
from telegram import Bot
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

DARK_BLUE = (13, 43, 92)
GOLD = (212, 160, 23)
WHITE = (255, 255, 255)
LIGHT_BLUE = (25, 65, 140)
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

SYSTEM_PROMPT = "Napyshi post ukrayinskoyu movoyu dlya Telegram kanalu pro finansy ta strakhuvannya v Ukrayini. Ton druzhniy. Zgaduy zakony. Dovzhyna 150-280 sliv. Emodzhi 3-6. Bez kheshteyhiv."

TOPICS = [
    {"name": "pension", "day": [0],
     "text": "Napyshi post pro pensiy ne nakopychennya. Zakon 1057-IV pro NPF. Stattya 166.3.3 PKU podatkova znyzhka. GRAWE Ukraine. Pensiya 3500 hrn. Treba kopychyty samostiyno.",
     "headline": "Пенсія в Україні: як не залишитись без копійки",
     "image_prompt": "Happy retired couple planning finances, warm home setting, coins and savings, professional photo, positive mood, no text",
     "poll_question": "Чи думали ви про пенсійні накопичення?",
     "poll_options": ["Так, вже накопичую", "Думав але не почав", "Ще ні, але планую", "Пенсія? Ще далеко"]},
    {"name": "stazh", "day": [2],
     "text": "Napyshi post pro trudovyy stazh. KZpP Ukrayiny. Zakon 1058-IV statti 24-26. Bez 15 rokiv pensiya ne pryznachayetsya. Dlya FOP moryakiv IT.",
     "headline": "Трудовий стаж: що треба знати кожному",
     "image_prompt": "Professional person working at desk, career documents, business setting, confident mood, no text",
     "poll_question": "Чи знаєте скільки років стажу у вас зараз?",
     "poll_options": ["Так, знаю точно", "Приблизно знаю", "Не знаю", "Піду перевіряти"]},
    {"name": "solidarna", "day": [2],
     "text": "Napyshi post pro derzhavnu pensiyu. Zakon 1058-IV stattya 27. Na 10 pensivoneriv 6 platnykiv. Pensiya 30 vidsotky zarplaty.",
     "headline": "Солідарна пенсія: чому держава не встигне",
     "image_prompt": "Scale with many elderly people and few young workers, financial balance concept, professional illustration style, no text",
     "poll_question": "На яку пенсію ви розраховуєте?",
     "poll_options": ["Тільки державна", "Державна + НПФ", "Тільки власні заощадження", "Ще не думав"]},
    {"name": "etrudova", "day": [2],
     "text": "Napyshi post pro elektronnu trudovu knyzhku. Zakon 1217-IX 2021. Postanova KMU 509. Yak pereviryt stazh v Diyi.",
     "headline": "Е-трудова: як перевірити стаж онлайн",
     "image_prompt": "Person using smartphone app for documents, modern digital Ukraine, bright office, positive mood, no text",
     "poll_question": "Чи перевіряли ви свій стаж в Дії?",
     "poll_options": ["Так, все гаразд", "Знайшов помилки", "Ще ні, піду перевірю", "Не знаю як"]},
    {"name": "dms", "day": [4],
     "text": "Napyshi post pro DMS medychne strakhuvannya. Zakon 85/96-VR. Stattya 142.1 PKU. GRAWE Ukraine 25 rokiv litsenziya NBU.",
     "headline": "ДМС: здоров'я вашої сім'ї під захистом",
     "image_prompt": "Happy healthy family with doctor, medical care concept, bright warm colors, professional photo, no text",
     "poll_question": "Чи має ваша сім'я ДМС?",
     "poll_options": ["Так, має", "Тільки я маю", "Ні, але хочу оформити", "Ні, не планую"]},
    {"name": "life", "day": [4],
     "text": "Napyshi post pro strakhuvannya zhyttya. Zakon 85/96-VR. Stattya 166.3.5 PKU znyzhka 2690 hrn. GRAWE zakhyst nakopychennya.",
     "headline": "Страхування життя: захист і накопичення разом",
     "image_prompt": "Family protected by umbrella shield, life insurance concept, warm professional photo, secure and happy, no text",
     "poll_question": "Чи є у вас страхування життя?",
     "poll_options": ["Так, вже оформив", "Розглядаю варіант", "Ще ні, цікаво дізнатись", "Ні, не потрібно"]},
    {"name": "kzpp", "day": [0],
     "text": "Napyshi post pro zminy KZpP. Zakon 2136-IX 2022. Zakon 3720-IX. Vplyv na stazh i pensiyu. Dlya FOP ta naymanykh.",
     "headline": "Зміни в КЗпП: що важливо знати у 2024",
     "image_prompt": "Ukrainian business law documents, professional lawyer office, modern setting, confident atmosphere, no text",
     "poll_question": "Чи слідкуєте за змінами трудового законодавства?",
     "poll_options": ["Так, постійно", "Інколи читаю", "Ні, не встигаю", "Мені розповів консультант"]},
]

COUNTER_FILE = "/tmp/post_counter.txt"

def get_counter():
    try:
        with open(COUNTER_FILE) as f:
            return int(f.read().strip())
    except:
        return 0

def inc_counter():
    c = get_counter() + 1
    with open(COUNTER_FILE, "w") as f:
        f.write(str(c))

def get_topic(day):
    matching = [t for t in TOPICS if day in t["day"]]
    return random.choice(matching if matching else TOPICS)

def wrap_text(draw, text, font, max_w):
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        if draw.textbbox((0,0), test, font=font)[2] > max_w and line:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    return lines

def create_varta_image(headline, photo_url=None):
    W, H, TOP_H = 1080, 1080, 420
    img = Image.new("RGB", (W, H), DARK_BLUE)
    draw = ImageDraw.Draw(img)

    for y in range(TOP_H):
        t = y / TOP_H
        draw.line([(0,y),(W,y)], fill=(
            int(DARK_BLUE[0] + (LIGHT_BLUE[0]-DARK_BLUE[0]) * t * 0.6),
            int(DARK_BLUE[1] + (LIGHT_BLUE[1]-DARK_BLUE[1]) * t * 0.6),
            int(DARK_BLUE[2] + (LIGHT_BLUE[2]-DARK_BLUE[2]) * t * 0.6),
        ))

    draw.rectangle([0, 0, W, 12], fill=GOLD)

    try:
        fb = ImageFont.truetype(FONT_BOLD, 46)
        ft = ImageFont.truetype(FONT_BOLD, 58)
        fs = ImageFont.truetype(FONT_REG, 30)
    except:
        fb = ft = fs = ImageFont.load_default()

    sx, sy = 60, 18
    draw.polygon([(sx,sy),(sx+50,sy),(sx+50,sy+45),(sx+25,sy+60),(sx,sy+45)], fill=GOLD)
    draw.polygon([(sx+8,sy+6),(sx+42,sy+6),(sx+42,sy+40),(sx+25,sy+52),(sx+8,sy+40)], fill=DARK_BLUE)

    brand = "FINANSOVA VARTA"
    bw = draw.textbbox((0,0), brand, font=fb)[2]
    draw.text(((W-bw)//2 + 30, 20), brand, font=fb, fill=GOLD)

    sub = "Oksana Berman  |  Kapital. Pensiia. Zakhyst."
    sw = draw.textbbox((0,0), sub, font=fs)[2]
    draw.text(((W-sw)//2, 80), sub, font=fs, fill=WHITE)

    draw.rectangle([60, 128, W-60, 134], fill=GOLD)

    lines = wrap_text(draw, headline, ft, W-100)
    total_h = len(lines) * 72
    start_y = 148 + max(0, (TOP_H - 148 - total_h) // 2)
    for i, ln in enumerate(lines):
        lw = draw.textbbox((0,0), ln, font=ft)[2]
        draw.text(((W-lw)//2 + 2, start_y+i*72+2), ln, font=ft, fill=(0,0,30))
        draw.text(((W-lw)//2, start_y+i*72), ln, font=ft, fill=WHITE)

    BOT_H = H - TOP_H
    if photo_url:
        try:
            r = requests.get(photo_url, timeout=20)
            photo = Image.open(io.BytesIO(r.content)).convert("RGB")
            photo = photo.resize((W, BOT_H), Image.LANCZOS)
            dark = Image.new("RGB", (W, BOT_H), (0,10,50))
            photo = Image.blend(photo, dark, 0.15)
            img.paste(photo, (0, TOP_H))
        except:
            for y in range(BOT_H):
                t = y / BOT_H
                draw.line([(0,TOP_H+y),(W,TOP_H+y)], fill=(int(20+30*t),int(55+40*t),int(130+50*t)))
    else:
        for y in range(BOT_H):
            t = y / BOT_H
            draw.line([(0,TOP_H+y),(W,TOP_H+y)], fill=(int(20+30*t),int(55+40*t),int(130+50*t)))

    draw.rectangle([0, H-68, W, H], fill=DARK_BLUE)
    draw.rectangle([0, H-70, W, H-64], fill=GOLD)
    ch = "@VartaFinance"
    chw = draw.textbbox((0,0), ch, font=fs)[2]
    draw.text(((W-chw)//2, H-54), ch, font=fs, fill=GOLD)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

async def generate_text(topic):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": topic["text"]}]
    )
    return msg.content[0].text

async def generate_photo(prompt):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    resp = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1
    )
    return resp.data[0].url

async def publish_post():
    bot = Bot(token=TELEGRAM_TOKEN)
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    topic = get_topic(now.weekday())
    counter = get_counter()
    use_image = (counter % 2 == 0)
    inc_counter()

    print("Topic: " + topic["name"] + " | " + ("image" if use_image else "poll"))

    try:
        text = await generate_text(topic)

        if use_image:
            print("Generating photo...")
            photo_url = await generate_photo(topic["image_prompt"])
            image_buf = create_varta_image(topic["headline"], photo_url)
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image_buf)
            await bot.send_message(chat_id=CHANNEL_ID, text=text)
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
    print("VartaFinance Bot started!")
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
