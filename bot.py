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
     "text": "Напиши пост про пенсійне накопичення в Україні. Згадай Закон 1057-IV про НПФ та статтю 166.3.3 ПКУ про податкову знижку. Акцент: середня пенсія 3500 грн — це виживання, а не життя. GRAWE Ukraine допомагає накопичувати.",
     "headline": "Пенсія в Україні: як не залишитись без копійки",
     "image_prompt": "Happy retired couple smiling, planning finances at home, warm cozy atmosphere, positive and hopeful mood, realistic photo, no text",
     "poll_question": "Чи думали ви про пенсійні накопичення?",
     "poll_options": ["Так, вже накопичую", "Думала але не почала", "Ще ні, але планую", "Пенсія? Ще далеко"]},
    {"name": "stazh", "day": [2],
     "text": "Напиши пост про трудовий стаж в Україні. Згадай КЗпП та Закон 1058-IV статті 24-26. Акцент: без 15 років стажу пенсія не призначається взагалі. Особливо важливо для ФОП, моряків, IT.",
     "headline": "Трудовий стаж: що треба знати кожному",
     "image_prompt": "Confident professional person at work desk, career documents, modern office, positive atmosphere, realistic photo, no text",
     "poll_question": "Чи знаєте скільки років стажу у вас зараз?",
     "poll_options": ["Так, знаю точно", "Приблизно знаю", "Не знаю", "Піду перевіряти"]},
    {"name": "solidarna", "day": [2],
     "text": "Напиши пост про солідарну державну пенсію. Згадай Закон 1058-IV статтю 27. Акцент: на 10 пенсіонерів лише 6 платників ЄСВ, пенсія покриває лише 30% зарплати. Держава не встигне.",
     "headline": "Солідарна пенсія: чому держава не встигне",
     "image_prompt": "Worried elderly couple looking at bills, financial stress concept, realistic photo, natural lighting, no text",
     "poll_question": "На яку пенсію ви розраховуєте?",
     "poll_options": ["Тільки державна", "Державна + НПФ", "Тільки власні заощадження", "Ще не думала"]},
    {"name": "etrudova", "day": [2],
     "text": "Напиши пост про електронну трудову книжку. Згадай Закон 1217-IX від 2021 року та постанову КМУ 509. Як перевірити стаж в Дії. Що робити якщо є помилки.",
     "headline": "Е-трудова: як перевірити стаж онлайн",
     "image_prompt": "Person using smartphone checking documents, Diia app concept, modern bright setting, Ukraine, no text",
     "poll_question": "Чи перевіряли ви свій стаж в Дії?",
     "poll_options": ["Так, все гаразд", "Знайшла помилки", "Ще ні, піду перевірю", "Не знаю як"]},
    {"name": "dms", "day": [4],
     "text": "Напиши пост про добровільне медичне страхування. Згадай Закон про страхування 85/96-ВР та статтю 142.1 ПКУ. GRAWE Ukraine — 25 років на ринку, ліцензія НБУ. Захист сім'ї під час війни.",
     "headline": "ДМС: здоров'я вашої сім'ї під захистом",
     "image_prompt": "Happy healthy family with doctor, warm clinic setting, care and protection concept, positive realistic photo, no text",
     "poll_question": "Чи має ваша сім'я ДМС?",
     "poll_options": ["Так, має", "Тільки я маю", "Ні, але хочу оформити", "Ні, не планую"]},
    {"name": "life", "day": [4],
     "text": "Напиши пост про страхування життя як інструмент захисту і накопичення. Згадай Закон 85/96-ВР та статтю 166.3.5 ПКУ — податкова знижка до 2690 грн на місяць. GRAWE: захист плюс накопичення.",
     "headline": "Страхування життя: захист і накопичення разом",
     "image_prompt": "Family protected under umbrella, security and love concept, warm colors, happy realistic photo, no text",
     "poll_question": "Чи є у вас страхування життя?",
     "poll_options": ["Так, вже оформила", "Розглядаю варіант", "Ще ні, цікаво дізнатись", "Ні, не потрібно"]},
    {"name": "kzpp", "day": [0],
     "text": "Напиши пост про зміни в трудовому законодавстві України. Згадай Закон 2136-IX від 2022 року та Закон 3720-IX. Як зміни впливають на стаж і майбутню пенсію для ФОП і найманих працівників.",
     "headline": "Зміни в КЗпП: що важливо знати у 2024",
     "image_prompt": "Ukrainian business professional reading documents, modern office, confident atmosphere, realistic photo, no text",
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
    W, H = 1080, 1080
    TOP_H = 380
    BOT_H = H - TOP_H

    img = Image.new("RGB", (W, H), DARK_BLUE)
    draw = ImageDraw.Draw(img)

    # Gradient top section
    for y in range(TOP_H):
        t = y / TOP_H
        draw.line([(0,y),(W,y)], fill=(
            int(DARK_BLUE[0] + (LIGHT_BLUE[0]-DARK_BLUE[0]) * t * 0.5),
            int(DARK_BLUE[1] + (LIGHT_BLUE[1]-DARK_BLUE[1]) * t * 0.5),
            int(DARK_BLUE[2] + (LIGHT_BLUE[2]-DARK_BLUE[2]) * t * 0.5),
        ))

    # Gold top stripe
    draw.rectangle([0, 0, W, 12], fill=GOLD)

    try:
        fb = ImageFont.truetype(FONT_BOLD, 44)
        ft = ImageFont.truetype(FONT_BOLD, 54)
        fs = ImageFont.truetype(FONT_REG, 28)
    except:
        fb = ft = fs = ImageFont.load_default()

    # Shield icon
    sx, sy = 55, 20
    draw.polygon([(sx,sy),(sx+46,sy),(sx+46,sy+42),(sx+23,sy+56),(sx,sy+42)], fill=GOLD)
    draw.polygon([(sx+7,sy+6),(sx+39,sy+6),(sx+39,sy+37),(sx+23,sy+49),(sx+7,sy+37)], fill=DARK_BLUE)

    # Brand name
    brand = "FINANSOVA VARTA"
    bw = draw.textbbox((0,0), brand, font=fb)[2]
    draw.text(((W-bw)//2 + 25, 22), brand, font=fb, fill=GOLD)

    # Tagline
    sub = "Oksana Berman  |  Kapital. Pensiia. Zakhyst."
    sw = draw.textbbox((0,0), sub, font=fs)[2]
    draw.text(((W-sw)//2, 78), sub, font=fs, fill=WHITE)

    # Gold divider
    draw.rectangle([60, 122, W-60, 128], fill=GOLD)

    # Headline - Ukrainian text
    lines = wrap_text(draw, headline, ft, W-100)
    total_h = len(lines) * 68
    start_y = 142 + max(10, (TOP_H - 142 - total_h) // 2)
    for i, ln in enumerate(lines):
        lw = draw.textbbox((0,0), ln, font=ft)[2]
        # Shadow
        draw.text(((W-lw)//2+2, start_y+i*68+2), ln, font=ft, fill=(0,0,30))
        # Text
        draw.text(((W-lw)//2, start_y+i*68), ln, font=ft, fill=WHITE)

    # Bottom photo
    if photo_url:
        try:
            r = requests.get(photo_url, timeout=20)
            photo = Image.open(io.BytesIO(r.content)).convert("RGB")
            photo = photo.resize((W, BOT_H), Image.LANCZOS)
            dark = Image.new("RGB", (W, BOT_H), (0, 10, 50))
            photo = Image.blend(photo, dark, 0.12)
            img.paste(photo, (0, TOP_H))
        except:
            for y in range(BOT_H):
                t = y / BOT_H
                draw.line([(0,TOP_H+y),(W,TOP_H+y)],
                    fill=(int(20+30*t), int(55+40*t), int(130+50*t)))
    else:
        for y in range(BOT_H):
            t = y / BOT_H
            draw.line([(0,TOP_H+y),(W,TOP_H+y)],
                fill=(int(20+30*t), int(55+40*t), int(130+50*t)))

    # Bottom bar
    draw.rectangle([0, H-65, W, H], fill=DARK_BLUE)
    draw.rectangle([0, H-67, W, H-61], fill=GOLD)
    ch = "@VartaFinance"
    chw = draw.textbbox((0,0), ch, font=fs)[2]
    draw.text(((W-chw)//2, H-52), ch, font=fs, fill=GOLD)

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
