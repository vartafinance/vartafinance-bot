import os
import asyncio
import random
import io
from datetime import datetime
import anthropic
import openai
import requests
import re

PENDING_POSTS = {}

from PIL import Image, ImageDraw, ImageFont
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@VartaFinance")
TEST_CHANNEL_ID = os.getenv("TEST_CHANNEL_ID", "")

SCHEDULE_HOUR = 10
SCHEDULE_MINUTE = 0
TIMEZONE = "Europe/Kiev"

# ─── SYSTEM PROMPTS ───────────────────────────────────────────────────────────

SYSTEM_INFO = """Ти — фінансовий консультант Оксана Берман, пишеш інформаційні пости для Telegram каналу @VartaFinance.

СТРУКТУРА ПОСТА:
1. ХУК — перший рядок ОБОВЯЗКОВО жирним: *твій хук тут*
2. ТІЛО — 2-3 абзаци, конкретно і просто
3. ВИСНОВОК — коротка думка без заклику писати в особисті

ПРАВИЛА:
- Пиши ТІЛЬКИ українською мовою
- Посилайся на конкретні закони України з номерами (ПКУ, КЗпП, ЦКУ тощо)
- Без списків і перерахувань
- Без лапок у тексті
- Тон нейтральний і інформативний
- Емодзі 2-3 штуки
- НЕ використовуй символи: _ [ ] ( ) ~ > # + - = | { } . ! у тексті
- НЕ закликай писати в особисті і НЕ рекламуй жодні продукти"""

SYSTEM_GRAWE = """Ти — фінансовий консультант Оксана Берман, пишеш короткі пости про страхову компанію GRAWE Ukraine для Telegram каналу @VartaFinance.

СТРУКТУРА ПОСТА:
1. ХУК — перший рядок ОБОВЯЗКОВО жирним: *твій хук тут*
2. ТІЛО — рівно 2 абзаци, коротко і по суті
3. ФАКТ — один цікавий факт або цифра в кінці

ПРАВИЛА:
- Пиши ТІЛЬКИ українською мовою
- Теми: рейтинги надійності, фінансові звіти, історія компанії, австрійський капітал, стабільність, нагороди, НБУ нагляд
- Без продажу і заклику до дії
- Без лапок у тексті
- Тон впевнений і фактичний
- Емодзі 2-3 штуки
- НЕ використовуй символи: _ [ ] ( ) ~ > # + - = | { } . ! у тексті"""

SYSTEM_SALES = """Ти — фінансовий консультант Оксана Берман, пишеш продажні пости для Telegram каналу @VartaFinance.

ВАЖЛИВО: Тільки GRAWE Ukraine. Щорічні відкладення від 25000 грн. НЕ згадуй НПФ.
Продукти GRAWE Ukraine:
- Накопичувальне страхування життя (приватна пенсія)
- Накопичення на дитину
- Захист від критичних хвороб
- Захист здоровя (ДМС)
- Страхування від нещасних випадків

СТРУКТУРА ПОСТА:
1. ХУК — перший рядок ОБОВЯЗКОВО жирним: *твій хук тут*
2. ТІЛО — 2 абзаци через реальну ситуацію або історію людини
3. ЗАКЛИК — запитання або заклик написати в особисті

ПРАВИЛА:
- Пиши ТІЛЬКИ українською мовою
- Можна позитивні або негативні (але не різкі) історії людей
- Без лапок у тексті
- Тон теплий і особистий
- Один конкретний закон України з номером
- Емодзі 2-4 штуки
- НЕ використовуй символи: _ [ ] ( ) ~ > # + - = | { } . ! у тексті"""

# ─── ТЕМИ ─────────────────────────────────────────────────────────────────────

INFO_TOPICS = [
    {"name": "pension_reform_1",
     "hook": "Пенсійна реформа 2024 — що реально змінилось для українців.",
     "text": "Напиши пост про пенсійну реформу в Україні. Закон 1058-IV про загальнообовязкове державне пенсійне страхування. Що змінилось, що залишилось, які ризики для майбутніх пенсіонерів."},
    {"name": "pension_deficit",
     "hook": "ПФУ дефіцитний вже 10 років поспіль. Хто платитиме твою пенсію?",
     "text": "Напиши пост про хронічний дефіцит Пенсійного фонду України. Закон 1058-IV. Солідарна система та її проблеми. Цифри і факти без реклами."},
    {"name": "stazh_insurance",
     "hook": "Трудовий стаж і страховий стаж — це різні речі. І різниця коштує тисячі гривень.",
     "text": "Напиши пост про різницю між трудовим і страховим стажем. КЗпП України статті 24-26 та Закон 1058-IV статті 24-26. Як рахується кожен і що впливає на пенсію."},
    {"name": "stazh_minimum",
     "hook": "Без 15 років страхового стажу пенсії не буде взагалі.",
     "text": "Напиши пост про мінімальний страховий стаж для отримання пенсії. Закон 1058-IV стаття 26. Що робити якщо стажу не вистачає, як можна донарахувати."},
    {"name": "stazh_abroad",
     "hook": "Робота за кордоном не рахується в українській пенсії автоматично.",
     "text": "Напиши пост про стаж при роботі за кордоном. Закон 1058-IV та міжнародні угоди України про соціальне забезпечення. Як зберегти і підтвердити стаж."},
    {"name": "esv_fop",
     "hook": "ФОП на 3 групі платить мінімальний ЄСВ. Пенсія буде відповідна.",
     "text": "Напиши пост про ЄСВ для ФОП. Закон 2464-VI про єдиний соціальний внесок. Як мінімальна сплата ЄСВ впливає на розмір майбутньої пенсії."},
    {"name": "fop_no_sick",
     "hook": "ФОП не має лікарняних. Захворів — не заробляєш. Це норма закону.",
     "text": "Напиши пост про відсутність соціальних гарантій у ФОП. КЗпП та Закон 2464-VI. Що ФОП втрачає порівняно з найманим працівником за законодавством."},
    {"name": "fop_stazh_close",
     "hook": "Закрив ФОП — страховий стаж зупинився. Навіть якщо ти продовжуєш працювати.",
     "text": "Напиши пост про зупинку страхового стажу після закриття ФОП. Закон 2464-VI про ЄСВ. Що відбувається зі стажем і як це виправити."},
    {"name": "trudova_knyzhka",
     "hook": "Трудова книжка — паперовий артефакт чи досі важливий документ?",
     "text": "Напиши пост про трудову книжку в Україні. КЗпП статті 48-49 та Закон 1217-IX про е-трудову. Що діє зараз, чи потрібна паперова книжка і як перевірити стаж в Дії."},
    {"name": "etrudova",
     "hook": "Електронна трудова книжка — як перевірити чи всі роки там є.",
     "text": "Напиши пост про е-трудову книжку та портал ПФУ. Закон 1217-IX від 2021. Як перевірити стаж через Дію або сайт ПФУ і що робити якщо знайшов помилки."},
    {"name": "moriak_pension",
     "hook": "Зарплата моряка — валюта. Пенсія — гривні. Різниця вбиває добробут.",
     "text": "Напиши пост про пенсійну проблему моряків в Україні. Закон 1058-IV та КЗпП. Як рахується стаж моряка, які особливості оподаткування і пенсійного страхування."},
    {"name": "moriak_esv",
     "hook": "Моряк працює через крюїнг. ЄСВ може не платитись взагалі.",
     "text": "Напиши пост про ЄСВ для моряків які працюють через крюїнгові компанії. Закон 2464-VI. Хто зобовязаний платити ЄСВ і як це перевірити."},
    {"name": "pku_nakladna",
     "hook": "Податкова знижка — гроші від держави які більшість українців просто не забирають.",
     "text": "Напиши пост про податкову знижку в Україні. Стаття 166 Податкового кодексу України. За що можна отримати знижку, хто має право, як подати декларацію."},
    {"name": "economy_war",
     "hook": "Що змінилось у трудовому законодавстві під час воєнного стану.",
     "text": "Напиши пост про зміни в трудовому законодавстві під час воєнного стану. Закон 2136-IX про організацію трудових відносин в умовах воєнного стану. Що змінилось для працівників і роботодавців."},
    {"name": "minimal_wage",
     "hook": "Мінімальна зарплата зросла. А мінімальна пенсія — ні.",
     "text": "Напиши пост про мінімальну зарплату і мінімальну пенсію в Україні. КЗпП стаття 95 та Закон 1058-IV. Чому вони ростуть по-різному і що це означає для пенсіонерів."},
    {"name": "women_stazh",
     "hook": "Жінки в Україні живуть довше але пенсія менша. Де логіка?",
     "text": "Напиши пост про пенсійну нерівність жінок в Україні. Закон 1058-IV та КЗпП. Декрет, догляд за дітьми і батьками — як це впливає на страховий стаж і розмір пенсії."},
    {"name": "dekret_stazh",
     "hook": "3 роки декрету — 3 роки мінімального стажу. Закон так і говорить.",
     "text": "Напиши пост про вплив декретної відпустки на пенсійний стаж. Закон 1058-IV та КЗпП стаття 179. Як рахується стаж під час декрету і що з цим можна зробити."},
    {"name": "gig_economy",
     "hook": "Гіг-контракт — зручно сьогодні, проблема на пенсії.",
     "text": "Напиши пост про гіг-контракти в Україні. Закон 1946-IX про Дія.City. Які соціальні гарантії є у гіг-спеціалістів і як це впливає на пенсійний стаж."},
    {"name": "pension_age",
     "hook": "Пенсійний вік підвищили. Але розмір пенсії не виріс.",
     "text": "Напиши пост про підвищення пенсійного віку в Україні. Закон 3668-VI. Що змінилось для чоловіків і жінок, які виключення існують."},
    {"name": "solidarna",
     "hook": "ПФУ не зберігає ваші гроші. Він одразу роздає їх пенсіонерам.",
     "text": "Напиши пост про солідарну пенсійну систему. Закон 1058-IV. Як працює солідарна система, чому вона в кризі і що це означає для тих хто зараз платить ЄСВ."},
]

GRAWE_TOPICS = [
    {"name": "grawe_history",
     "hook": "175 років — стільки існує група GRAWE. Це більше ніж вся незалежна Україна.",
     "text": "Напиши короткий пост про історію страхової групи GRAWE. Заснована в 1828 році в Граці Австрія. 27 років в Україні. Пережила дві світові війни кризи і продовжує працювати."},
    {"name": "grawe_nbu_rating",
     "hook": "НБУ вніс GRAWE Ukraine до переліку значимих страховиків. Таких лише 13 в країні.",
     "text": "Напиши короткий пост про включення GRAWE Ukraine до переліку значимих страховиків НБУ на 1 січня 2026. Положення НБУ 194. Що це означає — посилений нагляд і додаткові гарантії для клієнтів."},
    {"name": "grawe_report",
     "hook": "GRAWE Ukraine продовжує виплати навіть під час війни. Це не маркетинг — це факт зі звітності.",
     "text": "Напиши короткий пост про фінансову стабільність GRAWE Ukraine. Закон 85/96-ВР про страхування та вимоги НБУ до платоспроможності. Австрійський капітал як гарантія виплат."},
    {"name": "grawe_metlife",
     "hook": "MetLife пішла з України. GRAWE — залишилась. Різниця в підході.",
     "text": "Напиши короткий пост про те що PZU викупила MetLife Ukraine — звичайна консолідація ринку. На цьому фоні GRAWE 27 років без жодної зміни власника. Закон 85/96-ВР."},
    {"name": "grawe_austria",
     "hook": "Австрійський капітал в українській страховці — це не маркетинг це юридичний факт.",
     "text": "Напиши короткий пост про міжнародну структуру GRAWE Group. Материнська компанія Grazer Wechselseitige Versicherung AG — один з найстаріших страховиків Європи. Що це дає українському клієнту з точки зору надійності і Закону 85/96-ВР."},
    {"name": "grawe_stability",
     "hook": "GRAWE Ukraine пережила 1998, 2008, 2014 і 2022. Чотири кризи — нуль банкрутств.",
     "text": "Напиши короткий пост про стабільність GRAWE Ukraine через призму економічних криз. Закон 85/96-ВР та вимоги НБУ до резервів страхових компаній. Факти і цифри."},
    {"name": "grawe_license",
     "hook": "Не всі страхові компанії в Україні мають ліцензію на страхування життя. GRAWE — має.",
     "text": "Напиши короткий пост про ліцензування страхових компаній в Україні. Закон 85/96-ВР та регуляторні вимоги НБУ. Чому ліцензія на страхування життя — це серйозна вимога і що вона гарантує клієнту."},
]

SALES_TOPICS = [
    {"name": "sales_pension_story",
     "hook": "Він відкладав пенсію на потім. Потім настало в 58 років.",
     "text": "Напиши пост-історію про чоловіка який все життя відкладав думки про пенсію і опинився без накопичень у передпенсійному віці. Стаття 166.3.5 ПКУ про податкову знижку. Накопичувальне страхування GRAWE Ukraine як вихід навіть зараз. Заклик написати в особисті."},
    {"name": "sales_child",
     "hook": "Вона відкладала по 2000 грн на місяць. Доньці виповнилось 18 — і вона отримала внесок на квартиру.",
     "text": "Напиши пост про накопичення на дитину через GRAWE Ukraine. Позитивна історія мами яка почала рано. Закон 85/96-ВР. Скільки можна накопичити якщо починати з народження дитини. Щорічні відкладення від 25000 грн. Заклик написати в особисті."},
    {"name": "sales_critical",
     "hook": "Рак знаходять у кожного третього. Лікування коштує від 300 000 грн. Хто заплатить?",
     "text": "Напиши пост про захист від критичних хвороб GRAWE Ukraine. Реальна вартість онкологічного лікування в Україні. Закон 85/96-ВР. Як працює страховка при діагнозі. Заклик написати в особисті."},
    {"name": "sales_life_protect",
     "hook": "Якщо з тобою щось станеться завтра — твоя сімя протягне скільки місяців?",
     "text": "Напиши пост про захист сімї через страхування життя GRAWE Ukraine. Реальна історія сімї яка залишилась без годувальника. Закон 85/96-ВР та стаття 166.3.5 ПКУ. GRAWE: і захист і накопичення. Заклик написати в особисті."},
    {"name": "sales_private_pension",
     "hook": "Держава дає пенсію 4000 грн. Або ти сам копиш собі 40 000. Вибір є.",
     "text": "Напиши пост про приватну пенсію через накопичувальне страхування GRAWE Ukraine. Порівняй державну пенсію і власне накопичення. Стаття 166.3.5 ПКУ — держава повертає частину внесків. Щорічні відкладення від 25000 грн. Заклик написати в особисті."},
    {"name": "sales_early_start",
     "hook": "Починаєш в 30 — накопичуєш вдвічі більше ніж той хто почав в 40. Математика проста.",
     "text": "Напиши пост про силу раннього старту в накопиченні. Конкретний розрахунок: 25000 грн на рік з 30 років vs з 40 років через GRAWE Ukraine. Стаття 166.3.5 ПКУ. Заклик написати в особисті."},
    {"name": "sales_negative_story",
     "hook": "Він не встиг. Ця історія про його дружину яка залишилась сама з іпотекою.",
     "text": "Напиши пост — негативна але не різка історія про сімю яка не мала страхування життя і зіткнулась з фінансовими труднощами. Закон 85/96-ВР. GRAWE як рішення яке могло б захистити. Теплий тон без драми. Заклик написати в особисті."},
    {"name": "sales_fop_pension",
     "hook": "ФОП заробляє 3000 доларів зараз. Пенсія від держави буде 4000 гривень.",
     "text": "Напиши пост для ФОП про пенсійну проблему. Закон 1058-IV та мінімальний ЄСВ на 3 групі. Накопичувальне страхування GRAWE як власна пенсійна програма для ФОП. Щорічні відкладення від 25000 грн. Заклик написати в особисті."},
    {"name": "sales_moriak_family",
     "hook": "Чоловік в рейсі 9 місяців. Що станеться з сімєю якщо він не повернеться?",
     "text": "Напиши пост для дружин моряків про захист сімї. Реальні ризики професії моряка. Закон 85/96-ВР. GRAWE: страхування життя і накопичення навіть поки чоловік в рейсі. Заклик написати в особисті."},
    {"name": "sales_tax_return",
     "hook": "Держава повертає до 18% від суми страхового внеску. Більшість про це навіть не знає.",
     "text": "Напиши пост про податкову знижку на страхування життя. Стаття 166.3.5 Податкового кодексу України. Конкретний розрахунок: скільки можна повернути за рік. GRAWE Ukraine. Заклик написати в особисті."},
]

POLL_TOPICS = [
    {"question": "Чи знаєте скільки у вас страхового стажу?",
     "options": ["Так, знаю точно", "Приблизно знаю", "Не знаю", "Піду перевірю в Дії"]},
    {"question": "Чи є у вас фінансова подушка безпеки?",
     "options": ["Так, є на 6+ місяців", "Є на 1-3 місяці", "Формую зараз", "Ще немає"]},
    {"question": "Чи думаєте ви про пенсію вже зараз?",
     "options": ["Так, вже накопичую", "Думаю але не дію", "Ні, ще рано", "Держава подбає"]},
    {"question": "Якби ви втратили роботу завтра — на скільки вистачить грошей?",
     "options": ["Менше місяця", "1-3 місяці", "3-6 місяців", "Більше 6 місяців"]},
    {"question": "Чи користувались ви податковою знижкою?",
     "options": ["Так, щороку", "Один раз пробувала", "Не знала про це", "Не підходить мені"]},
    {"question": "Що для вас зараз важливіше?",
     "options": ["Захист від ризиків", "Накопичення на пенсію", "Накопичення для дітей", "Ще думаю"]},
    {"question": "Чи є у вас страхування життя?",
     "options": ["Так, накопичувальне", "Тільки від роботи", "Ні, немає", "Планую оформити"]},
]

# ─── АНТИПОВТОР ───────────────────────────────────────────────────────────────

USED_INFO_FILE = "/tmp/used_info.txt"
USED_GRAWE_FILE = "/tmp/used_grawe.txt"
USED_SALES_FILE = "/tmp/used_sales.txt"
USED_POLL_FILE = "/tmp/used_poll.txt"

def get_used(filepath):
    try:
        with open(filepath) as f:
            content = f.read().strip()
            return set(content.split(",")) if content else set()
    except:
        return set()

def save_used(filepath, used_set):
    with open(filepath, "w") as f:
        f.write(",".join(used_set))

def pick_topic(topics, used_file):
    used = get_used(used_file)
    available = [t for t in topics if t["name"] not in used]
    if not available:
        save_used(used_file, set())
        available = topics
    topic = random.choice(available)
    used = get_used(used_file)
    used.add(topic["name"])
    save_used(used_file, used)
    return topic

def pick_poll():
    used = get_used(USED_POLL_FILE)
    available = [i for i in range(len(POLL_TOPICS)) if str(i) not in used]
    if not available:
        save_used(USED_POLL_FILE, set())
        available = list(range(len(POLL_TOPICS)))
    idx = random.choice(available)
    used = get_used(USED_POLL_FILE)
    used.add(str(idx))
    save_used(USED_POLL_FILE, used)
    return POLL_TOPICS[idx]

# ─── ЗОБРАЖЕННЯ ───────────────────────────────────────────────────────────────

import random as _random

TOPIC_IMAGES = {
    "pension": ["Gemini_Generated_Image_cdldk2cdldk2cdld.png"],
    "stazh": ["Gemini_Generated_Image_es1igwes1igwes1i.png"],
    "etrudova": ["Gemini_Generated_Image_es1igwes1igwes1i.png"],
    "trudova": ["Gemini_Generated_Image_es1igwes1igwes1i.png"],
    "esv": ["Gemini_Generated_Image_xmzqshxmzqshxmzq.png"],
    "fop": ["Gemini_Generated_Image_xmzqshxmzqshxmzq.png", "img_youth_cafe.png"],
    "gig": ["Gemini_Generated_Image_xmzqshxmzqshxmzq.png"],
    "moriak": ["Gemini_Generated_Image_n0ipvdn0ipvdn0ip.png", "img_sailor_captain.png", "img_sailor_family.png", "img_sailor_wife.png"],
    "women": ["img_women_granny.png", "img_women_mom.png", "img_women_work.png"],
    "dekret": ["img_women_mom.png"],
    "minimal": ["Gemini_Generated_Image_cdldk2cdldk2cdld.png"],
    "economy": ["Gemini_Generated_Image_cdldk2cdldk2cdld.png"],
    "solidarna": ["Gemini_Generated_Image_cdldk2cdldk2cdld.png"],
    "pku": ["Gemini_Generated_Image_dhd5qadhd5qadhd5.png"],
    "grawe": ["Gemini_Generated_Image_4mfb284mfb284mfb.png"],
    "sales": ["Gemini_Generated_Image_4mfb284mfb284mfb.png"],
    "kzpp": ["Gemini_Generated_Image_dhd5qadhd5qadhd5.png"],
}

def get_topic_image(topic_name):
    import os as _os
    for key, img_files in TOPIC_IMAGES.items():
        if topic_name.startswith(key):
            available = []
            for img_file in img_files:
                path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), img_file)
                if _os.path.exists(path):
                    available.append(path)
            if available:
                return _random.choice(available)
    fallback = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "Gemini_Generated_Image_4mfb284mfb284mfb.png")
    return fallback if _os.path.exists(fallback) else None

# ─── ГЕНЕРАЦІЯ ТЕКСТУ ─────────────────────────────────────────────────────────

async def generate_text(system_prompt, hook, text_prompt):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = "*" + hook + "*\n\n" + text_prompt
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=600,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text

# ─── ЗОБРАЖЕННЯ SEND ──────────────────────────────────────────────────────────

async def send_image(bot, chat_id, topic_name):
    img_path = get_topic_image(topic_name)
    if not img_path:
        return None
    try:
        from PIL import Image as PILImage
        import io as _io
        pil_img = PILImage.open(img_path).convert("RGB")
        pil_img = pil_img.resize((800, 450), PILImage.LANCZOS)
        buf = _io.BytesIO()
        pil_img.save(buf, "JPEG", quality=75)
        image_bytes = buf.getvalue()
        buf.seek(0)
        await bot.send_photo(chat_id=chat_id, photo=buf)
        print("Image sent: " + img_path)
        return image_bytes
    except Exception as e:
        print("Image error: " + repr(e))
        return None

# ─── КНОПКИ ───────────────────────────────────────────────────────────────────

def build_test_keyboard(topic_name, with_consultation=False):
    forward_btn = InlineKeyboardButton("✅ З кнопкою", callback_data="forward_" + topic_name)
    forward_no_btn = InlineKeyboardButton("📨 Без кнопки", callback_data="forwardclean_" + topic_name)
    skip_btn = InlineKeyboardButton("❌ Не пересилати", callback_data="no_forward")
    consultation_btn = InlineKeyboardButton("💬 Хочу консультацію", url="https://t.me/BermanOdesa")
    if with_consultation:
        return InlineKeyboardMarkup([
            [consultation_btn],
            [forward_btn, forward_no_btn],
            [skip_btn]
        ])
    else:
        return InlineKeyboardMarkup([
            [forward_btn, forward_no_btn],
            [skip_btn]
        ])

def build_main_keyboard(with_consultation=False):
    if with_consultation:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Хочу консультацію", url="https://t.me/BermanOdesa")
        ]])
    return None

# ─── CALLBACK HANDLER ─────────────────────────────────────────────────────────

async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "no_forward":
        msg_id = str(query.message.message_id)
        post_data = PENDING_POSTS.get(msg_id)
        if post_data and post_data.get("with_button"):
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 Хочу консультацію", url="https://t.me/BermanOdesa")
            ]]))
        else:
            await query.edit_message_reply_markup(reply_markup=None)
        if msg_id in PENDING_POSTS:
            del PENDING_POSTS[msg_id]
        return

    if data.startswith("forward_") or data.startswith("forwardclean_"):
        clean = data.startswith("forwardclean_")
        msg_id = str(query.message.message_id)
        post_data = PENDING_POSTS.get(msg_id)

        if not post_data:
            await query.answer("Пост не знайдено або вже опубліковано 🤷", show_alert=True)
            return

        bot = context.bot
        main_keyboard = build_main_keyboard(with_consultation=(post_data.get("with_button") and not clean))

        # Беремо актуальний текст (після можливого редагування)
        current_text = query.message.text or post_data["text"]

        if post_data.get("image_bytes"):
            import io as _io
            buf = _io.BytesIO(post_data["image_bytes"])
            buf.seek(0)
            await bot.send_photo(chat_id=CHANNEL_ID, photo=buf)

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=current_text,
            parse_mode="Markdown",
            reply_markup=main_keyboard
        )

        if post_data.get("poll_question"):
            await bot.send_poll(
                chat_id=CHANNEL_ID,
                question=post_data["poll_question"],
                options=post_data["poll_options"],
                is_anonymous=True
            )

        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Опубліковано в основний", callback_data="done")
        ]]))

        del PENDING_POSTS[msg_id]
        print("Forwarded: " + post_data.get("topic_name", "?") + (" clean" if clean else " with btn"))

    if data == "done":
        await query.answer("Вже опубліковано ✅")


# ─── ПУБЛІКАЦІЯ ПОСТІВ ────────────────────────────────────────────────────────

async def publish_info_post(bot: Bot):
    """Пн/Ср — інформаційний пост"""
    target = TEST_CHANNEL_ID if TEST_CHANNEL_ID else CHANNEL_ID
    topic = pick_topic(INFO_TOPICS, USED_INFO_FILE)
    print("INFO: " + topic["name"])
    try:
        text = await generate_text(SYSTEM_INFO, topic["hook"], topic["text"])
        image_bytes = await send_image(bot, target, topic["name"])
        keyboard = build_test_keyboard(topic["name"], with_consultation=False) if TEST_CHANNEL_ID else None
        msg = await bot.send_message(chat_id=target, text=text, parse_mode="Markdown", reply_markup=keyboard)
        if TEST_CHANNEL_ID:
            PENDING_POSTS[str(msg.message_id)] = {
                "text": text, "with_button": False,
                "topic_name": topic["name"], "image_bytes": image_bytes,
                "poll_question": None, "poll_options": None,
            }
        print("Info post OK")
    except Exception as e:
        print("Info post error: " + repr(e))


async def publish_grawe_post(bot: Bot):
    """Чт — GRAWE пост"""
    target = TEST_CHANNEL_ID if TEST_CHANNEL_ID else CHANNEL_ID
    topic = pick_topic(GRAWE_TOPICS, USED_GRAWE_FILE)
    print("GRAWE: " + topic["name"])
    try:
        text = await generate_text(SYSTEM_GRAWE, topic["hook"], topic["text"])
        image_bytes = await send_image(bot, target, topic["name"])
        keyboard = build_test_keyboard(topic["name"], with_consultation=False) if TEST_CHANNEL_ID else None
        msg = await bot.send_message(chat_id=target, text=text, parse_mode="Markdown", reply_markup=keyboard)
        if TEST_CHANNEL_ID:
            PENDING_POSTS[str(msg.message_id)] = {
                "text": text, "with_button": False,
                "topic_name": topic["name"], "image_bytes": image_bytes,
                "poll_question": None, "poll_options": None,
            }
        print("GRAWE post OK")
    except Exception as e:
        print("GRAWE post error: " + repr(e))


async def publish_sales_post(bot: Bot):
    """Пт — продажний пост з кнопкою консультації"""
    target = TEST_CHANNEL_ID if TEST_CHANNEL_ID else CHANNEL_ID
    topic = pick_topic(SALES_TOPICS, USED_SALES_FILE)
    print("SALES: " + topic["name"])
    try:
        text = await generate_text(SYSTEM_SALES, topic["hook"], topic["text"])
        image_bytes = await send_image(bot, target, topic["name"])
        if TEST_CHANNEL_ID:
            keyboard = build_test_keyboard(topic["name"], with_consultation=True)
        else:
            keyboard = build_main_keyboard(with_consultation=True)
        msg = await bot.send_message(chat_id=target, text=text, parse_mode="Markdown", reply_markup=keyboard)
        if TEST_CHANNEL_ID:
            PENDING_POSTS[str(msg.message_id)] = {
                "text": text, "with_button": True,
                "topic_name": topic["name"], "image_bytes": image_bytes,
                "poll_question": None, "poll_options": None,
            }
        print("Sales post OK")
    except Exception as e:
        print("Sales post error: " + repr(e))


async def publish_weekly_poll(bot: Bot):
    """Ср — опитування тижня"""
    target = TEST_CHANNEL_ID if TEST_CHANNEL_ID else CHANNEL_ID
    poll = pick_poll()
    print("POLL: " + poll["question"])
    try:
        await bot.send_poll(
            chat_id=target,
            question=poll["question"],
            options=poll["options"],
            is_anonymous=True
        )
        if TEST_CHANNEL_ID:
            forward_btn = InlineKeyboardButton("✅ Переслати опитування", callback_data="forward_poll")
            skip_btn = InlineKeyboardButton("❌ Не пересилати", callback_data="no_forward")
            keyboard = InlineKeyboardMarkup([[forward_btn, skip_btn]])
            msg = await bot.send_message(
                chat_id=target,
                text="👆 Опитування тижня — переслати в основний?",
                reply_markup=keyboard
            )
            PENDING_POSTS[str(msg.message_id)] = {
                "text": "👆 Опитування тижня",
                "with_button": False, "topic_name": "poll",
                "image_bytes": None,
                "poll_question": poll["question"],
                "poll_options": poll["options"],
            }
        print("Poll OK")
    except Exception as e:
        print("Poll error: " + repr(e))


# ─── НОВИНИ ───────────────────────────────────────────────────────────────────

PENSION_KEYWORDS = ["пенсі", "пфу", "пенсійн", "стаж", "єсв", "накопич", "пенсіонер", "виплат", "солідарн"]
GRAWE_KEYWORDS = ["grawe", "страхуван", "накопич", "поліс", "виплат", "захист"]

def get_last_id(filepath):
    try:
        with open(filepath) as f:
            return f.read().strip()
    except:
        return ""

def save_last_id(filepath, news_id):
    with open(filepath, "w") as f:
        f.write(news_id)

async def fetch_channel_news(channel_name, keywords, last_file):
    try:
        r = requests.get("https://t.me/s/" + channel_name, timeout=15)
        if r.status_code != 200:
            return None
        posts = re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', r.text, re.DOTALL)
        ids = re.findall(r'data-post="' + channel_name + r'/([0-9]+)"', r.text)
        if not posts or not ids:
            return None
        last_id = get_last_id(last_file)
        for post_id, post_html in zip(ids, posts):
            if post_id == last_id:
                break
            text = re.sub(r'<[^>]+>', '', post_html).strip()
            text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            if len(text) < 50:
                continue
            if any(kw in text.lower() for kw in keywords):
                save_last_id(last_file, ids[0])
                return text
        if ids:
            save_last_id(last_file, ids[0])
        return None
    except Exception as e:
        print("Channel " + channel_name + " error: " + repr(e))
        return None

async def fetch_minsoc_news():
    return await fetch_channel_news("MinSocUA", PENSION_KEYWORDS, "/tmp/last_minsoc.txt")

async def fetch_grawe_news():
    return await fetch_channel_news("graweinukraine", GRAWE_KEYWORDS, "/tmp/last_grawe.txt")

async def fetch_pfu_news():
    try:
        r = requests.get("https://www.pfu.gov.ua/news/", timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        titles = re.findall(r'<h[23][^>]*class="[^"]*title[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', r.text)
        if not titles:
            return None
        last_url = get_last_id("/tmp/last_pfu.txt")
        for url, title in titles[:10]:
            title = title.strip()
            if not title or len(title) < 10 or url == last_url:
                continue
            if any(kw in title.lower() for kw in PENSION_KEYWORDS):
                save_last_id("/tmp/last_pfu.txt", url)
                full_url = url if url.startswith("http") else "https://www.pfu.gov.ua" + url
                try:
                    article = requests.get(full_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                    text = re.sub(r'<[^>]+>', ' ', article.text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    idx = text.find(title)
                    text = title + ". " + text[idx+len(title):idx+len(title)+600] if idx > 0 else title
                except:
                    text = title
                return text
        if titles:
            save_last_id("/tmp/last_pfu.txt", titles[0][0])
        return None
    except Exception as e:
        print("PFU error: " + repr(e))
        return None

async def publish_news_post(bot: Bot, news_text, target):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (
        "Ось новина:\n\n" + news_text +
        "\n\nПерепиши для Telegram каналу @VartaFinance. "
        "Стиль: 2-3 абзаци, українською, без лапок, тон теплий. "
        "Починай з жирного хуку *текст*. "
        "Поясни що ця новина означає для звичайної людини. "
        "НЕ додавай заклик писати в особисті."
    )
    msg = client.messages.create(
        model="claude-opus-4-5", max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    post_text = msg.content[0].text
    image_bytes = await send_image(bot, target, "kzpp")
    keyboard = build_test_keyboard("news", with_consultation=False) if TEST_CHANNEL_ID else None
    msg_out = await bot.send_message(chat_id=target, text=post_text, parse_mode="Markdown", reply_markup=keyboard)
    if TEST_CHANNEL_ID:
        PENDING_POSTS[str(msg_out.message_id)] = {
            "text": post_text, "with_button": False,
            "topic_name": "news", "image_bytes": image_bytes,
            "poll_question": None, "poll_options": None,
        }
    print("News post OK")

async def check_and_publish_news(bot: Bot):
    target = TEST_CHANNEL_ID if TEST_CHANNEL_ID else CHANNEL_ID
    for name, func in [("MinSocUA", fetch_minsoc_news), ("GRAWE", fetch_grawe_news), ("PFU", fetch_pfu_news)]:
        print("Checking " + name + "...")
        try:
            news = await func()
            if news:
                await publish_news_post(bot, news, target)
                print("Published from " + name)
                return
        except Exception as e:
            print("Error " + name + ": " + repr(e))
    print("No news today")


# ─── РУЧНІ ПОСТИ В ТЕСТ-КАНАЛІ ───────────────────────────────────────────────

async def handle_test_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    if not msg:
        return
    chat_id_str = str(msg.chat_id)
    test_id_str = str(TEST_CHANNEL_ID)
    username_match = msg.chat.username and TEST_CHANNEL_ID.lstrip("@") == msg.chat.username
    if chat_id_str != test_id_str and not username_match:
        return
    if msg.reply_markup:
        return
    text = msg.text or msg.caption
    if not text:
        return
    msg_id = str(msg.message_id)
    keyboard = build_test_keyboard("manual", with_consultation=False)
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=msg.chat_id,
            message_id=msg.message_id,
            reply_markup=keyboard
        )
        PENDING_POSTS[msg_id] = {
            "text": text, "with_button": True,
            "topic_name": "manual", "image_bytes": None,
            "poll_question": None, "poll_options": None,
        }
        print("Buttons added to manual post: " + msg_id)
    except Exception as e:
        print("Manual post buttons error: " + repr(e))


# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    print("VartaFinance Bot started!")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CallbackQueryHandler(handle_forward))
    if TEST_CHANNEL_ID:
        app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_test_channel_post))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    bot = app.bot
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Пн — інформаційний
    scheduler.add_job(publish_info_post, CronTrigger(day_of_week="0", hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone=TIMEZONE), kwargs={"bot": bot})
    # Ср — інформаційний + опитування через 5 хв
    scheduler.add_job(publish_info_post, CronTrigger(day_of_week="2", hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone=TIMEZONE), kwargs={"bot": bot})
    scheduler.add_job(publish_weekly_poll, CronTrigger(day_of_week="2", hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE + 5, timezone=TIMEZONE), kwargs={"bot": bot})
    # Чт — GRAWE
    scheduler.add_job(publish_grawe_post, CronTrigger(day_of_week="3", hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone=TIMEZONE), kwargs={"bot": bot})
    # Пт — продажний
    scheduler.add_job(publish_sales_post, CronTrigger(day_of_week="4", hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone=TIMEZONE), kwargs={"bot": bot})
    # Щодня 21:00 — новини
    scheduler.add_job(check_and_publish_news, CronTrigger(hour=21, minute=0, timezone=TIMEZONE), kwargs={"bot": bot})

    scheduler.start()

    print("Test post in 5 sec...")
    await asyncio.sleep(5)
    await publish_info_post(bot=bot)
    print("Running...")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
