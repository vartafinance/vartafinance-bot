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
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

SYSTEM_PROMPT = """Ти — фінансовий консультант Оксана Берман, пишеш пости для Telegram каналу @VartaFinance.

СТРУКТУРА ПОСТА:
1. ХУК — перший рядок жирним через **текст**. Влучний, несподіваний або провокаційний. Приклади: "Більшість українців втратять 70% пенсії. І навіть не здогадуються.", "Ти платиш ЄСВ роками — але стаж може не зарахуватись."
2. ТІЛО — 2 абзаци, розкриваєш думку просто і конкретно
3. ЗАКЛИК — коротке запитання або заклик написати в особисті

ПРАВИЛА:
- Пиши ТІЛЬКИ українською мовою
- Без списків і перерахувань
- Без лапок у тексті
- Без звернень типу подруга, друже, колего
- Тон теплий і простий
- Згадай один конкретний закон України з номером
- Емодзі 2-4 штуки"""

TOPICS = [
    {"name": "pension", "day": [0],
     "text": "Напиши пост про пенсійне накопичення в Україні. Згадай Закон 1057-IV про НПФ та статтю 166.3.3 ПКУ. Середня пенсія 3500 грн — це виживання. GRAWE Ukraine допомагає накопичувати.",
     "image_prompt": "A real photo of a happy retired couple in their 60s sitting together at home, warm afternoon sunlight through window, candid moment, shot on Sony A7III 85mm f1.4, shallow depth of field, photojournalism style, no text, no watermark",
     "poll_question": "Чи думали ви про пенсійні накопичення?",
     "poll_options": ["Так, вже накопичую", "Думала але не почала", "Ще ні, але планую", "Пенсія? Ще далеко"]},
    {"name": "stazh", "day": [2],
     "text": "Напиши пост про трудовий стаж в Україні. Згадай КЗпП та Закон 1058-IV статті 24-26. Без 15 років стажу пенсія не призначається. Для ФОП, моряків, IT.",
     "image_prompt": "A real photo of a confident woman in her 30s working at a desk in a modern office, natural window light, candid documentary style, shot on Sony A7III 50mm, sharp focus, no text, no watermark",
     "poll_question": "Чи знаєте скільки років стажу у вас зараз?",
     "poll_options": ["Так, знаю точно", "Приблизно знаю", "Не знаю", "Піду перевіряти"]},
    {"name": "solidarna", "day": [2],
     "text": "Напиши пост про солідарну державну пенсію. Згадай Закон 1058-IV статтю 27. На 10 пенсіонерів 6 платників ЄСВ, пенсія лише 30% зарплати.",
     "image_prompt": "A real photo of a thoughtful woman in her 40s sitting at kitchen table with notebook and calculator, warm natural light, documentary photography, shot on Sony A7III, no text, no watermark",
     "poll_question": "На яку пенсію ви розраховуєте?",
     "poll_options": ["Тільки державна", "Державна + НПФ", "Тільки власні заощадження", "Ще не думала"]},
    {"name": "etrudova", "day": [2],
     "text": "Напиши пост про електронну трудову книжку. Згадай Закон 1217-IX від 2021 та постанову КМУ 509. Як перевірити стаж в Дії.",
     "image_prompt": "Person smiling using smartphone, modern bright setting, no text no writing",
     "poll_question": "Чи перевіряли ви свій стаж в Дії?",
     "poll_options": ["Так, все гаразд", "Знайшла помилки", "Ще ні, піду перевірю", "Не знаю як"]},
    {"name": "dms", "day": [4],
     "text": "Напиши пост про добровільне медичне страхування. Згадай Закон 85/96-ВР та статтю 142.1 ПКУ. GRAWE Ukraine — 25 років на ринку.",
     "image_prompt": "A real photo of a happy family with a friendly doctor in a bright modern clinic, genuine smiles, documentary style, shot on Sony A7III, warm light, no text, no watermark",
     "poll_question": "Чи має ваша сім'я ДМС?",
     "poll_options": ["Так, має", "Тільки я маю", "Ні, але хочу оформити", "Ні, не планую"]},
    {"name": "life", "day": [4],
     "text": "Напиши пост про страхування життя. Згадай Закон 85/96-ВР та статтю 166.3.5 ПКУ — знижка до 2690 грн на місяць. GRAWE: захист і накопичення.",
     "image_prompt": "A real photo of a happy family of four in a sunny park, parents and children laughing together, golden hour light, candid documentary photography, shot on Sony A7III 85mm, no text, no watermark",
     "poll_question": "Чи є у вас страхування життя?",
     "poll_options": ["Так, вже оформила", "Розглядаю варіант", "Ще ні, цікаво дізнатись", "Ні, не потрібно"]},
    {"name": "kzpp", "day": [0],
     "text": "Напиши пост про зміни в КЗпП. Згадай Закон 2136-IX від 2022 та Закон 3720-IX. Як впливає на стаж і пенсію.",
     "image_prompt": "A real photo of a professional Ukrainian woman reading documents at a modern office desk, confident expression, natural window light, documentary style, shot on Sony A7III, no text, no watermark",
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

def create_varta_image(photo_url=None):
    W, H = 1080, 1080
    TOP_H = 64

    img = Image.new("RGB", (W, H), DARK_BLUE)
    draw = ImageDraw.Draw(img)

    if photo_url:
        try:
            r = requests.get(photo_url, timeout=20)
            photo = Image.open(io.BytesIO(r.content)).convert("RGB")
            photo = photo.resize((W, H), Image.LANCZOS)
            img.paste(photo, (0, 0))
            draw = ImageDraw.Draw(img)
        except Exception as e:
            print("photo err: " + str(e))

    overlay = Image.new("RGBA", (W, TOP_H), (13, 43, 92, 220))
    img.paste(overlay, (0, 0), overlay)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 7], fill=GOLD)

    try:
        fb = ImageFont.truetype(FONT_BOLD, 36)
    except:
        fb = ImageFont.load_default()

    part1 = "Finansova "
    part2 = "VARTA"
    w1 = draw.textbbox((0,0), part1, font=fb)[2]
    w2 = draw.textbbox((0,0), part2, font=fb)[2]
    sx = (W - w1 - w2) // 2
    draw.text((sx, 16), part1, font=fb, fill=WHITE)
    draw.text((sx + w1, 16), part2, font=fb, fill=GOLD)

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
            image_buf = create_varta_image(photo_url)
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image_buf)
            await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")
            print("Posted with image OK")
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")
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
