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

LIGHT_BLUE = (30, 100, 200)
DARK_BLUE = (13, 43, 92)
GOLD = (212, 160, 23)
WHITE = (255, 255, 255)
FONT_BOLD = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

SYSTEM_PROMPT = """Ти — фінансовий консультант Оксана Берман, пишеш пости для свого Telegram каналу @VartaFinance.

ПРАВИЛА:
- Пиши ТІЛЬКИ українською мовою, без латиниці
- 2-3 абзаци, одна головна думка
- Без списків і перерахувань
- Без лапок у тексті
- Тон як порада подрузі — тепло і просто
- Згадай один закон України
- Закінчи коротким запитанням або закликом написати в особисті
- Емодзі 2-4 штуки"""

TOPICS = [
    {"name": "pension", "day": [0],
     "text": "Напиши пост про пенсійне накопичення в Україні. Згадай Закон 1057-IV про НПФ та статтю 166.3.3 ПКУ. Акцент: середня пенсія 3500 грн — це виживання. GRAWE Ukraine допомагає накопичувати.",
     "headline": "Пенсія в Україні: як не залишитись без копійки",
     "image_prompt": "Happy smiling retired couple enjoying life at home, warm sunlight, positive mood, realistic photo, no text",
     "poll_question": "Чи думали ви про пенсійні накопичення?",
     "poll_options": ["Так, вже накопичую", "Думала але не почала", "Ще ні, але планую", "Пенсія? Ще далеко"]},
    {"name": "stazh", "day": [2],
     "text": "Напиши пост про трудовий стаж в Україні. Згадай КЗпП та Закон 1058-IV статті 24-26. Без 15 років стажу пенсія не призначається. Для ФОП, моряків, IT.",
     "headline": "Трудовий стаж: що треба знати кожному",
     "image_prompt": "Confident professional person working at modern desk, bright office, positive atmosphere, realistic photo, no text",
     "poll_question": "Чи знаєте скільки років стажу у вас зараз?",
     "poll_options": ["Так, знаю точно", "Приблизно знаю", "Не знаю", "Піду перевіряти"]},
    {"name": "solidarna", "day": [2],
     "text": "Напиши пост про солідарну державну пенсію. Згадай Закон 1058-IV статтю 27. На 10 пенсіонерів 6 платників ЄСВ, пенсія лише 30% зарплати.",
     "headline": "Солідарна пенсія: чому держава не встигне",
     "image_prompt": "Thoughtful middle aged woman planning finances at home, calculator and notebook, natural light, realistic photo, no text",
     "poll_question": "На яку пенсію ви розраховуєте?",
     "poll_options": ["Тільки державна", "Державна + НПФ", "Тільки власні заощадження", "Ще не думала"]},
    {"name": "etrudova", "day": [2],
     "text": "Напиши пост про електронну трудову книжку. Згадай Закон 1217-IX від 2021 та постанову КМУ 509. Як перевірити стаж в Дії.",
     "headline": "Е-трудова: як перевірити стаж онлайн",
     "image_prompt": "Person smiling using smartphone app, modern bright setting, checking documents digitally, no text",
     "poll_question": "Чи перевіряли ви свій стаж в Дії?",
     "poll_options": ["Так, все гаразд", "Знайшла помилки", "Ще ні, піду перевірю", "Не знаю як"]},
    {"name": "dms", "day": [4],
     "text": "Напиши пост про добровільне медичне страхування. Згадай Закон 85/96-ВР та статтю 142.1 ПКУ. GRAWE Ukraine — 25 років на ринку.",
     "headline": "ДМС: здоров'я вашої сім'ї під захистом",
     "image_prompt": "Happy healthy family with doctor in bright clinic, care and warmth, positive realistic photo, no text",
     "poll_question": "Чи має ваша сім'я ДМС?",
     "poll_options": ["Так, має", "Тільки я маю", "Ні, але хочу оформити", "Ні, не планую"]},
    {"name": "life", "day": [4],
     "text": "Напиши пост про страхування життя. Згадай Закон 85/96-ВР та статтю 166.3.5 ПКУ — знижка до 2690 грн на місяць. GRAWE: захист плюс накопичення.",
     "headline": "Страхування життя: захист і накопичення разом",
     "image_prompt": "Happy family outdoors in park, parents and children, sunny day, love and security, realistic photo, no text",
     "poll_question": "Чи є у вас страхування життя?",
     "poll_options": ["Так, вже оформила", "Розглядаю варіант", "Ще ні, цікаво дізнатись", "Ні, не потрібно"]},
    {"name": "kzpp", "day": [0],
     "text": "Напиши пост про зміни в КЗпП. Згадай Закон 2136-IX від 2022 та Закон 3720-IX. Як впливає на стаж і пенсію для ФОП і найманих.",
     "headline": "Зміни в КЗпП: що важливо знати у 2024",
     "image_prompt": "Professional woman reading documents at desk, modern office, focused and confident, realistic photo, no text"},
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
    W, H = 1080, 1080
    TOP_H = 480
    BOT_H = H - TOP_H

    img = Image.new("RGB", (W, H), LIGHT_BLUE)
    draw = ImageDraw.Draw(img)

    for y in range(TOP_H):
        t = y / TOP_H
        draw.line([(0,y),(W,y)], fill=(
            int(LIGHT_BLUE[0] + (DARK_BLUE[0]-LIGHT_BLUE[0]) * t),
            int(LIGHT_BLUE[1] + (DARK_BLUE[1]-LIGHT_BLUE[1]) * t),
            int(LIGHT_BLUE[2] + (DARK_BLUE[2]-LIGHT_BLUE[2]) * t),
        ))

    try:
        f_brand = ImageFont.truetype(FONT_BOLD, 28)
        f_title = ImageFont.truetype(FONT_BOLD, 72)
    except:
        f_brand = f_title = ImageFont.load_default()

    part1 = "Finansova "
    part2 = "VARTA"
    w1 = draw.textbbox((0,0), part1, font=f_brand)[2]
    w2 = draw.textbbox((0,0), part2, font=f_brand)[2]
    sx = (W - w1 - w2) // 2
    draw.text((sx, 18), part1, font=f_brand, fill=WHITE)
    draw.text((sx + w1, 18), part2, font=f_brand, fill=GOLD)

    draw.rectangle([40, 58, W-40, 63], fill=GOLD)

    lines = wrap_text(draw, headline, f_title, W-80)
    total_h = len(lines) * 88
    start_y = 75 + max(10, (TOP_H - 75 - total_h) // 2)
    for i, ln in enumerate(lines):
        lw = draw.textbbox((0,0), ln, font=f_title)[2]
        draw.text(((W-lw)//2+3, start_y+i*88+3), ln, font=f_title, fill=(0,20,80))
        draw.text(((W-lw)//2, start_y+i*88), ln, font=f_title, fill=WHITE)

    if photo_url:
        try:
            r = requests.get(photo_url, timeout=20)
            photo = Image.open(io.BytesIO(r.content)).convert("RGB")
            photo = photo.resize((W, BOT_H), Image.LANCZOS)
            img.paste(photo, (0, TOP_H))
        except:
            draw.rectangle([0, TOP_H, W, H], fill=(20,55,130))
    else:
        draw.rectangle([0, TOP_H, W, H], fill=(20,55,130))

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

async def generate_text(topic):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=600,
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
            poll_options = topic.get("poll_options", ["Так", "Ні", "Ще думаю"])
            poll_question = topic.get("poll_question", "Що думаєте?")
            await bot.send_poll(
                chat_id=CHANNEL_ID,
                question=poll_question,
                options=poll_options,
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
