import os
import asyncio
import random
import io
from datetime import datetime
import anthropic
import openai
import requests
import json as _json

PENDING_POSTS = {}  # Store posts waiting for approval

import re
from PIL import Image, ImageDraw, ImageFont
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@VartaFinance")
TEST_CHANNEL_ID = os.getenv("TEST_CHANNEL_ID", "")
MINSOC_CHANNEL = "@MinSocUA"

SCHEDULE_DAYS = "0,2,4"  # Mon, Wed, Fri
SCHEDULE_HOUR = 10
SCHEDULE_MINUTE = 0
TIMEZONE = "Europe/Kiev"

DARK_BLUE = (13, 43, 92)
GOLD = (212, 160, 23)
WHITE = (255, 255, 255)
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

SYSTEM_PROMPT = """Ти — фінансовий консультант Оксана Берман, пишеш пости для Telegram каналу @VartaFinance.

ВАЖЛИВО: Коли згадуєш накопичення — завжди пиши про ЩОРІЧНІ відкладення, не щомісячні. Для прикладу використовуй суму 25000 грн на рік. НЕ згадуй НПФ або недержавні пенсійні фонди. Згадуй тільки страхову компанію GRAWE Ukraine.
Продукти GRAWE Ukraine які можна згадувати:
- Накопичувальне страхування життя (приватна пенсія)
- Накопичення на дитину
- Захист від критичних хвороб
- Захист здоров'я (ДМС)
- Страхування від нещасних випадків

СТРУКТУРА ПОСТА:
1. ХУК — перший рядок ОБОВЯЗКОВО жирним. Використай саме цей формат: *твій хук тут* (зірочка на початку і в кінці). Хук має бути влучним і несподіваним. Наприклад: *Більшість українців залишаться без пенсії. І навіть не здогадуються.*
2. ТІЛО — 2 абзаци, розкриваєш думку просто і конкретно
3. ЗАКЛИК — коротке запитання або заклик написати в особисті

ПРАВИЛА:
- Пиши ТІЛЬКИ українською мовою
- Без списків і перерахувань  
- Без лапок у тексті
- Без звернень типу подруга, друже, колего
- Тон теплий і простий
- Згадай один конкретний закон України з номером
- Емодзі 2-4 штуки
- НЕ використовуй символи: _ [ ] ( ) ~ > # + - = | { } . ! у тексті"""

TOPICS = [
    # ПЕНСІЯ І ДЕРЖАВА
    {"name": "pension_1", "day": [0,1,2,3,4],
     "hook": "Середня пенсія в Україні — 3800 грн. Це менше за комуналку взимку.",
     "text": "Напиши пост про те що середня пенсія в Україні 3800 грн менше за комуналку взимку. Закон 1058-IV про пенсійне страхування. Акцент на тому що треба накопичувати самостійно через GRAWE Ukraine.",
     "image_prompt": "Warm lifestyle photography, elderly Ukrainian couple enjoying retirement at cozy home, warm kitchen, coffee cups, genuine smiles, photorealistic, no text, no watermark",
     "poll_question": "Чи вистачає вам пенсії на базові потреби?",
     "poll_options": ["Так, вистачає", "Ледве вистачає", "Не вистачає", "Ще не на пенсії"]},
    {"name": "pension_2", "day": [0,1,2,3,4],
     "hook": "ПФУ дефіцитний вже 10 років поспіль. Хто платитиме твою пенсію?",
     "text": "Напиши пост про дефіцит Пенсійного фонду України вже 10 років. Закон 1058-IV. Акцент: система не витримає — треба особисте накопичення.",
     "image_prompt": "Warm lifestyle photography, worried middle aged Ukrainian couple looking at documents, warm living room, natural light, photorealistic, no text, no watermark",
     "poll_question": "Чи довіряєте ви державній пенсійній системі?",
     "poll_options": ["Так, довіряю", "Частково", "Ні, не довіряю", "Не думав про це"]},
    {"name": "pension_3", "day": [0,1,2,3,4],
     "hook": "Пенсійний вік підвищили. Але розмір пенсії не виріс.",
     "text": "Напиши пост про те що пенсійний вік підвищили але пенсія не виросла. Закон 3668-VI про підвищення пенсійного віку. Акцент: GRAWE дозволяє вийти на пенсію раніше.",
     "image_prompt": "Warm lifestyle photography, tired Ukrainian woman still working at laptop late, warm home office, evening light, photorealistic, no text, no watermark",
     "poll_question": "В якому віці плануєте вийти на пенсію?",
     "poll_options": ["До 55 років", "55-60 років", "60-65 років", "Буду працювати довго"]},
    {"name": "pension_4", "day": [0,1,2,3,4],
     "hook": "В Польщі середня пенсія — 800 євро. В Україні — 100. Різниця в накопиченнях.",
     "text": "Напиши пост про порівняння пенсій в Польщі та Україні. Різниця в системі накопичення. Закон 1057-IV про НПФ. GRAWE як рішення.",
     "image_prompt": "Warm lifestyle photography, happy retired Ukrainian couple enjoying life outdoors, warm sunny day, freedom, photorealistic, no text, no watermark",
     "poll_question": "Чи знаєте скільки отримують пенсіонери в сусідніх країнах?",
     "poll_options": ["Так, знаю", "Приблизно", "Ні, не знаю", "Не цікавилась"]},
    {"name": "pension_5", "day": [0,1,2,3,4],
     "hook": "ПФУ не інвестує твої гроші. Він просто перерозподіляє їх сьогодні.",
     "text": "Напиши пост про те як працює солідарна система — гроші не накопичуються а одразу виплачуються. Закон 1058-IV. НПФ як альтернатива де гроші реально накопичуються.",
     "image_prompt": "Warm lifestyle photography, Ukrainian woman planning finances with notebook at kitchen table, warm morning light, coffee, photorealistic, no text, no watermark",
     "poll_question": "Чи знали ви що ПФУ не зберігає ваші гроші?",
     "poll_options": ["Так, знала", "Не знала", "Не розумію як це", "Байдуже"]},

    # ТРУДОВИЙ СТАЖ
    {"name": "stazh_1", "day": [0,1,2,3,4],
     "hook": "Ти можеш пропрацювати 20 років і отримати мінімальну пенсію. Ось чому.",
     "text": "Напиши пост про те що стаж і розмір пенсії — різні речі. КЗпП та Закон 1058-IV статті 24-26. Акцент на страховому стажі vs загальному.",
     "image_prompt": "Warm lifestyle photography, Ukrainian woman reviewing documents at home desk, warm cozy setting, cup of tea, photorealistic, no text, no watermark",
     "poll_question": "Чи знаєте різницю між страховим і трудовим стажем?",
     "poll_options": ["Так, знаю", "Не зовсім", "Ні, не знаю", "Перший раз чую"]},
    {"name": "stazh_2", "day": [0,1,2,3,4],
     "hook": "Робота за кордоном не рахується в українській пенсії автоматично.",
     "text": "Напиши пост про стаж при роботі за кордоном. Закон 1058-IV та міжнародні угоди України. Як зберегти стаж якщо працюєш за кордоном.",
     "image_prompt": "Warm lifestyle photography, young Ukrainian woman working on laptop from cozy home abroad, warm atmosphere, photorealistic, no text, no watermark",
     "poll_question": "Чи працювали ви або ваші близькі за кордоном?",
     "poll_options": ["Так, я", "Так, близькі", "Ні", "Планую"]},
    {"name": "stazh_3", "day": [0,1,2,3,4],
     "hook": "Без 15 років страхового стажу пенсії не буде взагалі.",
     "text": "Напиши пост про мінімальний страховий стаж 15 років. Закон 1058-IV стаття 26. Що робити якщо стажу не вистачає.",
     "image_prompt": "Warm lifestyle photography, Ukrainian man checking documents with concerned expression, warm home setting, photorealistic, no text, no watermark",
     "poll_question": "Чи знаєте скільки у вас страхового стажу?",
     "poll_options": ["Так, знаю точно", "Приблизно знаю", "Не знаю", "Піду перевірю"]},
    {"name": "stazh_4", "day": [0,1,2,3,4],
     "hook": "Якщо роботодавець не платив ЄСВ — ці роки вилетять зі стажу.",
     "text": "Напиши пост про ризик роботи без офіційного оформлення. Закон 2464-VI про ЄСВ. Як перевірити чи платив роботодавець.",
     "image_prompt": "Warm lifestyle photography, Ukrainian woman checking smartphone with relief, bright cozy apartment, natural light, photorealistic, no text, no watermark",
     "poll_question": "Чи перевіряли ви чи платив роботодавець ЄСВ за вас?",
     "poll_options": ["Так, перевіряла", "Ні, але перевірю", "Не знаю як", "Працюю офіційно"]},
    {"name": "stazh_5", "day": [0,1,2,3,4],
     "hook": "Перевір свій стаж в Дії зараз. Там можуть бути помилки.",
     "text": "Напиши пост про перевірку стажу в Дії. Закон 1217-IX від 2021 про е-трудову. Що робити якщо знайшов помилки.",
     "image_prompt": "Warm lifestyle photography, Ukrainian woman smiling at phone, bright sunny home interior, morning atmosphere, photorealistic, no text, no watermark",
     "poll_question": "Чи перевіряли ви свій стаж в Дії?",
     "poll_options": ["Так, все гаразд", "Знайшла помилки", "Ще ні, перевірю", "Не знаю як"]},

    # СТРАХУВАННЯ ЖИТТЯ
    {"name": "life_1", "day": [0,1,2,3,4],
     "hook": "Якщо з тобою щось трапиться — твоя сім'я залишиться без доходу на скільки місяців?",
     "text": "Напиши пост про захист сім'ї через страхування життя. Закон 85/96-ВР про страхування. GRAWE Ukraine — надійний захист.",
     "image_prompt": "Warm lifestyle photography, happy Ukrainian family of four in cozy living room, warm afternoon light, genuine laughter, photorealistic, no text, no watermark",
     "poll_question": "На скільки місяців вистачить заощаджень вашій сім'ї без вашого доходу?",
     "poll_options": ["До 1 місяця", "1-3 місяці", "3-6 місяців", "Більше 6 місяців"]},
    {"name": "life_2", "day": [0,1,2,3,4],
     "hook": "Страхування життя — це не витрата. Це єдиний внесок який повертається.",
     "text": "Напиши пост про накопичувальне страхування життя. Закон 85/96-ВР та стаття 166.3.5 ПКУ. GRAWE: захист плюс накопичення плюс повернення.",
     "image_prompt": "Warm lifestyle photography, confident Ukrainian woman signing documents at bright kitchen table, warm natural light, photorealistic, no text, no watermark",
     "poll_question": "Чи знали ви що страхування життя може бути накопичувальним?",
     "poll_options": ["Так, знала", "Не знала", "Цікаво дізнатись більше", "Вже маю поліс"]},
    {"name": "life_3", "day": [0,1,2,3,4],
     "hook": "Поки ти молодий — страховка коштує копійки. Потім — набагато дорожче.",
     "text": "Напиши пост про те що вартість страхування залежить від віку. Закон 85/96-ВР. Чим раніше починаєш — тим дешевше і більше накопичуєш.",
     "image_prompt": "Warm lifestyle photography, young Ukrainian couple discussing future plans together, warm cozy home, coffee cups on table, photorealistic, no text, no watermark",
     "poll_question": "В якому віці ви вперше задумались про страхування?",
     "poll_options": ["До 30 років", "30-40 років", "40-50 років", "Ще не думала"]},
    {"name": "life_4", "day": [0,1,2,3,4],
     "hook": "Податкова знижка на страхування життя — до 2690 грн на місяць назад.",
     "text": "Напиши пост про податкову знижку на страхування життя. Стаття 166.3.5 ПКУ. Як отримати гроші назад від держави.",
     "image_prompt": "Warm lifestyle photography, happy Ukrainian woman receiving good news on phone, bright warm home interior, photorealistic, no text, no watermark",
     "poll_question": "Чи користувались ви податковою знижкою?",
     "poll_options": ["Так, користуюсь", "Не знала про це", "Хочу дізнатись як", "Не підходить мені"]},
    {"name": "life_5", "day": [0,1,2,3,4],
     "hook": "Один нещасний випадок без страховки може знищити всі заощадження сім'ї.",
     "text": "Напиши пост про фінансові ризики без страхування. Закон 85/96-ВР. Реальна вартість лікування в Україні. GRAWE як захист.",
     "image_prompt": "Warm lifestyle photography, caring Ukrainian family together at home, warm evening atmosphere, parents and children, photorealistic, no text, no watermark",
     "poll_question": "Чи є у вас страхування від нещасних випадків?",
     "poll_options": ["Так, є", "Тільки на роботі", "Ні, немає", "Не думала про це"]},

    # ФОП І САМОЗАЙНЯТІ
    {"name": "fop_1", "day": [0,1,2,3,4],
     "hook": "ФОП не має лікарняних. Захворів — не заробляєш.",
     "text": "Напиши пост про відсутність соціальних гарантій у ФОП. КЗпП та Закон 2464-VI. ДМС і страхування як вирішення.",
     "image_prompt": "Warm lifestyle photography, Ukrainian self-employed woman working from home, warm home office, looking tired but determined, photorealistic, no text, no watermark",
     "poll_question": "Чи є у вас ФОП або самозайнятість?",
     "poll_options": ["Так, ФОП", "Самозайнятий", "Найманий працівник", "Інше"]},
    {"name": "fop_2", "day": [0,1,2,3,4],
     "hook": "IT-спеціаліст заробляє 3000 доларів. А пенсія буде 4000 гривень.",
     "text": "Напиши пост про пенсію IT-спеціалістів ФОП. Закон 1058-IV та мінімальний ЄСВ на 3 групі. НПФ і GRAWE як рішення.",
     "image_prompt": "Warm lifestyle photography, young Ukrainian IT professional at desk thinking, warm modern apartment, laptop open, photorealistic, no text, no watermark",
     "poll_question": "Чи думають IT-спеціалісти про свою пенсію?",
     "poll_options": ["Так, накопичую", "Думаю але не дію", "Ні, ще молодий", "Планую виїхати"]},
    {"name": "fop_3", "day": [0,1,2,3,4],
     "hook": "Закрив ФОП — страховий стаж зупинився. Навіть якщо ти працюєш.",
     "text": "Напиши пост про стаж після закриття ФОП. Закон 2464-VI про ЄСВ. Що робити щоб стаж не зупинявся.",
     "image_prompt": "Warm lifestyle photography, Ukrainian entrepreneur looking at documents with concern, warm cozy home office, photorealistic, no text, no watermark",
     "poll_question": "Чи знали ви що при закритті ФОП стаж зупиняється?",
     "poll_options": ["Так, знала", "Не знала", "У мене немає ФОП", "Цікаво дізнатись більше"]},

    # МОРЯКИ
    {"name": "moriak_1", "day": [0,1,2,3,4],
     "hook": "Зарплата моряка — валюта. Пенсія — гривні. Різниця вбиває.",
     "text": "Напиши пост про пенсійну проблему моряків. Зарплата у валюті але пенсія в гривнях. Закон 1058-IV. GRAWE дозволяє накопичувати у стабільних інструментах.",
     "image_prompt": "Warm lifestyle photography, Ukrainian sailor reuniting with family at home, warm emotional reunion moment, photorealistic, no text, no watermark",
     "poll_question": "Чи є серед ваших близьких моряки?",
     "poll_options": ["Так, чоловік", "Так, інші родичі", "Ні", "Я сам моряк"]},
    {"name": "moriak_2", "day": [0,1,2,3,4],
     "hook": "Страхування життя для моряка — це не розкіш. Це базова безпека сім'ї.",
     "text": "Напиши пост про страхування для моряків. Закон 85/96-ВР. Ризики професії та захист сім'ї. GRAWE спеціальні програми.",
     "image_prompt": "Warm lifestyle photography, Ukrainian woman with children at cozy home, warm interior, waiting atmosphere, photorealistic, no text, no watermark",
     "poll_question": "Чи має ваш чоловік-моряк страхування життя?",
     "poll_options": ["Так, має", "Тільки робоче", "Ні, немає", "Не моряк"]},
    {"name": "moriak_3", "day": [0,1,2,3,4],
     "hook": "Дружина моряка часто не працює. Її стаж — нульовий.",
     "text": "Напиши пост про стаж дружини моряка. КЗпП та Закон 1058-IV. Як накопичити стаж і захиститись якщо не працюєш офіційно.",
     "image_prompt": "Warm lifestyle photography, Ukrainian woman at home managing household thoughtfully, warm natural light, photorealistic, no text, no watermark",
     "poll_question": "Чи думали ви про власну пенсію якщо не працюєте офіційно?",
     "poll_options": ["Так, думала", "Не думала", "Є чоловікова пенсія", "Хочу дізнатись більше"]},

    # МОЛОДЬ
    {"name": "youth_1", "day": [0,1,2,3,4],
     "hook": "Почав накопичувати в 25 — матимеш вдвічі більше ніж той хто почав в 35.",
     "text": "Напиши пост про силу складних відсотків і ранній старт. Закон 1057-IV про НПФ. Розрахунок: 500 грн на місяць з 25 років vs з 35 років.",
     "image_prompt": "Warm lifestyle photography, young Ukrainian man smiling while planning future, bright modern apartment, natural light, photorealistic, no text, no watermark",
     "poll_question": "В якому віці ви почали думати про накопичення?",
     "poll_options": ["До 25 років", "25-30 років", "30-40 років", "Ще не почала"]},
    {"name": "youth_2", "day": [0,1,2,3,4],
     "hook": "Перша робота без офіційного оформлення — перші роки без стажу.",
     "text": "Напиши пост про важливість офіційного оформлення з першої роботи. КЗпП стаття 24. Як ці роки впливають на пенсію.",
     "image_prompt": "Warm lifestyle photography, young Ukrainian woman excited at first job, warm professional setting, confident, photorealistic, no text, no watermark",
     "poll_question": "Ваша перша робота була офіційною?",
     "poll_options": ["Так, офіційна", "Частково", "Ні, неофіційна", "Ще не працювала"]},

    # ЖІНКИ І СІМ'Я
    {"name": "women_1", "day": [0,1,2,3,4],
     "hook": "Жінки в Україні живуть довше. Але пенсія менша — бо стаж менший.",
     "text": "Напиши пост про пенсійну нерівність жінок. Декрет, догляд за дітьми та батьками. Закон 1058-IV. GRAWE як особистий захист.",
     "image_prompt": "Warm lifestyle photography, Ukrainian woman in her 50s looking thoughtfully out window, warm home interior, photorealistic, no text, no watermark",
     "poll_question": "Чи думали ви що жінки отримують меншу пенсію?",
     "poll_options": ["Так, знала", "Не знала", "Це несправедливо", "Маю своє рішення"]},
    {"name": "women_2", "day": [0,1,2,3,4],
     "hook": "3 роки декрету — 3 роки мінімального стажу. Це впливає на пенсію.",
     "text": "Напиши пост про вплив декрету на пенсію. Закон 1058-IV та КЗпП. Як компенсувати втрачений стаж через страхування.",
     "image_prompt": "Warm lifestyle photography, happy Ukrainian mother with baby at home, warm cozy nursery, genuine love, photorealistic, no text, no watermark",
     "poll_question": "Чи знали ви що декрет впливає на розмір пенсії?",
     "poll_options": ["Так, знала", "Не знала", "У мене є діти", "Планую мати дітей"]},
    {"name": "women_3", "day": [0,1,2,3,4],
     "hook": "Вийти на пенсію в 60 — і прожити ще 25 років. Чим?",
     "text": "Напиши пост про тривалість пенсійного періоду для жінок. Закон 1058-IV. 25 років на пенсії — скільки грошей потрібно і де їх взяти.",
     "image_prompt": "Warm lifestyle photography, active happy elderly Ukrainian woman enjoying retirement outdoors, warm sunny day, photorealistic, no text, no watermark",
     "poll_question": "Як плануєте фінансово забезпечити себе на пенсії?",
     "poll_options": ["Державна пенсія", "Накопичення + пенсія", "Діти допоможуть", "Ще не думала"]},

    # ВІЙНА І НЕВИЗНАЧЕНІСТЬ
    {"name": "war_1", "day": [0,1,2,3,4],
     "hook": "Під час війни особливо важливо мати фінансову подушку.",
     "text": "Напиши пост про фінансову безпеку під час війни. Закон 85/96-ВР. GRAWE продовжує виплати навіть в умовах воєнного стану.",
     "image_prompt": "Warm lifestyle photography, calm Ukrainian family feeling safe at home together, warm cozy living room, photorealistic, no text, no watermark",
     "poll_question": "Чи є у вас фінансова подушка безпеки?",
     "poll_options": ["Так, є", "Невелика", "Намагаюсь створити", "Немає"]},
    {"name": "war_2", "day": [0,1,2,3,4],
     "hook": "GRAWE Ukraine продовжує виплати навіть в умовах воєнного стану.",
     "text": "Напиши пост про надійність GRAWE під час війни. Закон 85/96-ВР та ліцензія НБУ. Австрійський капітал як гарантія стабільності.",
     "image_prompt": "Warm lifestyle photography, relieved Ukrainian woman receiving good financial news, warm home setting, smile, photorealistic, no text, no watermark",
     "poll_question": "Чи важлива для вас надійність страхової компанії?",
     "poll_options": ["Дуже важлива", "Важлива", "Не головне", "Ще не думала"]},
    {"name": "war_3", "day": [0,1,2,3,4],
     "hook": "В умовах невизначеності — фіксований захист важливіший за ризиковані інвестиції.",
     "text": "Напиши пост про консервативні інструменти захисту під час нестабільності. Закон 85/96-ВР. Страхування як стабільна основа фінансового плану.",
     "image_prompt": "Warm lifestyle photography, Ukrainian couple planning finances calmly together, warm home atmosphere, notebook on table, photorealistic, no text, no watermark",
     "poll_question": "Що для вас зараз важливіше?",
     "poll_options": ["Захист від ризиків", "Накопичення", "І те і інше", "Ще думаю"]},

    # ПСИХОЛОГІЯ ГРОШЕЙ
    {"name": "psych_1", "day": [0,1,2,3,4],
     "hook": "Найпоширеніша відмовка: почну відкладати коли буде більше грошей.",
     "text": "Напиши пост про відкладання фінансових рішень. Закон 1057-IV про НПФ. 500 грн зараз кращі ніж 5000 грн через 10 років.",
     "image_prompt": "Warm lifestyle photography, motivated Ukrainian woman making positive decision, bright warm home, determined expression, photorealistic, no text, no watermark",
     "poll_question": "Що заважає вам почати накопичувати?",
     "poll_options": ["Мало грошей", "Не знаю як", "Не довіряю системі", "Вже накопичую"]},
    {"name": "psych_2", "day": [0,1,2,3,4],
     "hook": "Люди більше планують відпустку ніж пенсію. І дивуються результату.",
     "text": "Напиши пост про пріоритети у фінансовому плануванні. Закон 1057-IV. Пенсія — це та сама відпустка тільки на 20 років.",
     "image_prompt": "Warm lifestyle photography, Ukrainian woman planning on laptop at cozy kitchen, warm home atmosphere, coffee, photorealistic, no text, no watermark",
     "poll_question": "Скільки часу ви витрачаєте на планування пенсії vs відпустки?",
     "poll_options": ["Більше на пенсію", "Однаково", "Більше на відпустку", "Не планую ні те ні інше"]},
    {"name": "psych_3", "day": [0,1,2,3,4],
     "hook": "Пенсія — це не про старість. Це про свободу вибору.",
     "text": "Напиши пост про фінансову свободу через пенсійне накопичення. Закон 1057-IV про НПФ. Можливість вийти на пенсію коли хочеш а не коли мусиш.",
     "image_prompt": "Warm lifestyle photography, active happy Ukrainian woman enjoying free time outdoors, warm sunny day, freedom, photorealistic, no text, no watermark",
     "poll_question": "Що для вас означає пенсія?",
     "poll_options": ["Свобода вибору", "Відпочинок", "Вимушена зупинка", "Ще не думала"]},
    {"name": "psych_4", "day": [0,1,2,3,4],
     "hook": "Найдорожча помилка — починати пізно.",
     "text": "Напиши пост про вартість зволікання з накопиченням. Закон 1057-IV. Конкретний розрахунок: різниця між стартом в 30 і в 45 років.",
     "image_prompt": "Warm lifestyle photography, determined Ukrainian woman making important financial decision, bright warm home, photorealistic, no text, no watermark",
     "poll_question": "Коли ви плануєте почати або вже почали накопичувати?",
     "poll_options": ["Вже накопичую", "Почну цього року", "Ще думаю", "Не знаю з чого почати"]},

    # БЮДЖЕТ
    {"name": "budget_1", "day": [0,1,2,3,4],
     "text": "Напиши пост про особистий бюджет. Правило 50/30/20 — 50% на необхідне, 30% на бажане, 20% на накопичення. Як це працює для українців. Без лапок, 2-3 абзаци.",
     "hook": "Більшість українців не знають куди йдуть їхні гроші. А ти знаєш?",
     "image_prompt": "Ukrainian woman planning budget at home with notebook and calculator, warm cozy atmosphere, illustration style",
     "poll_question": "Чи ведете ви особистий бюджет?",
     "poll_options": ["Так, веду регулярно", "Іноді записую", "Ні, але хочу почати", "Ні, не бачу сенсу"]},
    {"name": "budget_2", "day": [0,1,2,3,4],
     "text": "Напиши пост про фінансові цілі. Як правильно ставити фінансові цілі на рік. SMART метод для особистих фінансів. Конкретні приклади для українців.",
     "hook": "Без фінансової цілі гроші завжди кудись зникають самі.",
     "image_prompt": "Ukrainian person writing financial goals in notebook, motivated expression, bright modern home, illustration style",
     "poll_question": "Чи маєте ви фінансову ціль на цей рік?",
     "poll_options": ["Так, конкретна ціль", "Є приблизне розуміння", "Ні, але задумаюсь", "Ні"]},
    {"name": "budget_3", "day": [0,1,2,3,4],
     "text": "Напиши пост про щоденні фінансові звички які допомагають заощаджувати. 5 простих звичок які змінюють фінансове життя. Без моралізування, практично.",
     "hook": "Багатство — це не про великі доходи. Це про щоденні маленькі рішення.",
     "image_prompt": "Happy Ukrainian family saving money in piggy bank, cozy home, warm light, illustration style",
     "poll_question": "Яка ваша головна фінансова звичка?",
     "poll_options": ["Відкладаю частину доходу", "Веду бюджет", "Уникаю кредитів", "Поки немає"]},

    # ЗАХИСТ ВІД ІНФЛЯЦІЇ
    {"name": "inflation_1", "day": [0,1,2,3,4],
     "text": "Напиши пост про інфляцію в Україні і як вона знецінює заощадження. Статистика НБУ. Як захистити гроші від інфляції через страхування GRAWE Ukraine.",
     "hook": "Гроші під матрацом щороку втрачають 10-15% вартості. Твої теж.",
     "image_prompt": "Ukrainian woman looking worried at rising prices chart, home setting, illustration style",
     "poll_question": "Чи думали ви як захистити гроші від інфляції?",
     "poll_options": ["Так, вже захищаю", "Думала але не знаю як", "Ні, не думала", "Хочу дізнатись більше"]},
    {"name": "inflation_2", "day": [0,1,2,3,4],
     "text": "Напиши пост про ОВДП та інші інструменти захисту від інфляції в Україні. Порівняй з накопичувальним страхуванням GRAWE. Що краще для звичайної людини.",
     "hook": "Депозит в банку вже не рятує від інфляції. Що тоді рятує?",
     "image_prompt": "Ukrainian couple discussing financial instruments at home, documents and laptop, warm atmosphere, illustration style",
     "poll_question": "Де зберігаєте свої заощадження?",
     "poll_options": ["В банку на депозиті", "В страховій компанії", "В валюті", "Ще думаю"]},
    {"name": "inflation_3", "day": [0,1,2,3,4],
     "text": "Напиши пост про те як накопичувальне страхування захищає від інфляції краще ніж готівка. GRAWE Ukraine — як це працює на практиці. Закон 85/96-ВР.",
     "hook": "Готівка вдома — це не заощадження. Це повільна втрата грошей.",
     "image_prompt": "Ukrainian woman making smart financial decision, confident smile, modern home office, illustration style",
     "poll_question": "Чи знали ви що накопичувальне страхування захищає від інфляції?",
     "poll_options": ["Так, знала", "Не знала", "Розкажіть більше", "Маю поліс GRAWE"]},

    # ФІНАНСОВА ПОДУШКА
    {"name": "cushion_1", "day": [0,1,2,3,4],
     "text": "Напиши пост про фінансову подушку безпеки. Скільки місяців витрат мати в резерві. Як створити подушку якщо зараз немає зайвих грошей. Практичні кроки.",
     "hook": "Якщо ти втратиш роботу завтра — на скільки місяців вистачить грошей?",
     "image_prompt": "Ukrainian family feeling safe and secure at home, financial protection concept, warm cozy interior, illustration style",
     "poll_question": "На скільки місяців вистачить ваших заощаджень?",
     "poll_options": ["Менше 1 місяця", "1-3 місяці", "3-6 місяців", "Більше 6 місяців"]},
    {"name": "cushion_2", "day": [0,1,2,3,4],
     "text": "Напиши пост про різницю між фінансовою подушкою і страхуванням. Чому потрібне і те і інше. GRAWE як другий рівень захисту після подушки. Закон 85/96-ВР.",
     "hook": "Фінансова подушка рятує на 3-6 місяців. А що потім?",
     "image_prompt": "Ukrainian woman planning two-level financial protection, notebook with plan, bright home, illustration style",
     "poll_question": "Чи є у вас фінансова подушка безпеки?",
     "poll_options": ["Так, є", "Невелика є", "Формую зараз", "Ще немає"]},
    {"name": "cushion_3", "day": [0,1,2,3,4],
     "text": "Напиши пост про фінансову безпеку під час війни. Чому особливо важливо мати резерв і страхування зараз. GRAWE продовжує виплати навіть в умовах воєнного стану.",
     "hook": "Під час війни фінансова подушка — це не розкіш. Це необхідність.",
     "image_prompt": "Calm confident Ukrainian family at home feeling financially protected, warm safe atmosphere, illustration style",
     "poll_question": "Чи збільшили ви свою фінансову подушку під час війни?",
     "poll_options": ["Так, збільшила", "Намагаюсь", "Ні, немає можливості", "Не думала про це"]},

    # METLIFE PZU
    {"name": "grawe_metlife", "day": [0,1,2,3,4],
     "text": """Напиши пост про те що польська група PZU викупила 100% акцій MetLife Ukraine. Це звичайна бізнес-угода — консолідація ринку страхування в Східній Європі. Усі зобов'язання перед клієнтами залишаються в силі. Використай це як привід розповісти про GRAWE Ukraine — австрійський капітал з 175-річною історією, 27 років в Україні без жодних злиттів і змін власника. Поки ринок консолідується — GRAWE продовжує стабільно працювати. Закон 85/96-ВР. Щорічні відкладення від 25000 грн.""",
     "hook": "MetLife іде з України. А GRAWE — залишається.",
     "image_prompt": "Confident Ukrainian family choosing reliable insurance, stable home atmosphere, security concept, illustration style",
     "poll_question": "Чи важлива для вас стабільність власника страхової компанії?",
     "poll_options": ["Дуже важлива", "Важлива", "Не думала про це", "Головне умови полісу"]},

    # GRAWE NBU
    {"name": "grawe_nbu", "day": [0,1,2,3,4],
     "text": """Напиши пост про те що НБУ вперше оприлюднив перелік значимих страховиків станом на 1 січня 2026 року і GRAWE Ukraine страхування життя увійшла до цього списку. Всього 13 компаній, лише дві — у сегменті страхування життя. Поясни що це означає для клієнта — посилений нагляд НБУ, надійність, захист. Згадай Закон 85/96-ВР та Положення НБУ №194. GRAWE 27 років на ринку — пережила всі кризи і продовжує виплати під час війни.""",
     "hook": "НБУ офіційно визнав GRAWE Ukraine значимою страховою компанією. Що це означає для тебе?",
     "image_prompt": "Ukrainian family feeling financially protected, official document with seal, warm secure atmosphere, illustration style",
     "poll_question": "Чи знали ви що НБУ контролює надійність страхових компаній?",
     "poll_options": ["Так, знала", "Не знала", "Це важливо для мене", "Хочу дізнатись більше"]},

    # GRAWE І ПРОДУКТИ
    {"name": "grawe_1", "day": [0,1,2,3,4],
     "hook": "GRAWE в Україні вже 28 років. Пережили дефолт, кризу і війну.",
     "text": "Напиши пост про надійність GRAWE Ukraine. Закон 85/96-ВР та ліцензія НБУ. 28 років на українському ринку — факти.",
     "image_prompt": "Warm lifestyle photography, confident Ukrainian professional woman at warm modern office, natural light, trustworthy, photorealistic, no text, no watermark",
     "poll_question": "Чи важливо для вас що страхова компанія пережила кризи?",
     "poll_options": ["Дуже важливо", "Важливо", "Не головне", "Перший раз чую про GRAWE"]},
    {"name": "grawe_2", "day": [0,1,2,3,4],
     "hook": "Австрійський капітал в українській страховці — це про надійність.",
     "text": "Напиши пост про міжнародну підтримку GRAWE. Закон 85/96-ВР. Австрійська група GRAWE — один з найстаріших страховиків Європи.",
     "image_prompt": "Warm lifestyle photography, secure happy Ukrainian family in cozy living room, warm light, protected feeling, photorealistic, no text, no watermark",
     "poll_question": "Чи знали ви що GRAWE — це австрійська компанія?",
     "poll_options": ["Так, знала", "Не знала", "Це важливо для мене", "Байдуже звідки"]},
]

COUNTER_FILE = "/tmp/varta_counter.txt"

def get_counter():
    try:
        with open(COUNTER_FILE) as f:
            return int(f.read().strip())
    except:
        import datetime
        val = datetime.datetime.now().timetuple().tm_yday * 3
        with open(COUNTER_FILE, "w") as f:
            f.write(str(val))
        return val

def inc_counter():
    c = get_counter() + 1
    with open(COUNTER_FILE, "w") as f:
        f.write(str(c))

import random as _random

TOPIC_IMAGES = {
    "pension": ["Gemini_Generated_Image_cdldk2cdldk2cdld.png"],
    "stazh": ["Gemini_Generated_Image_es1igwes1igwes1i.png"],
    "solidarna": ["Gemini_Generated_Image_cdldk2cdldk2cdld.png"],
    "etrudova": ["Gemini_Generated_Image_es1igwes1igwes1i.png"],
    "life": ["Gemini_Generated_Image_4mfb284mfb284mfb.png"],
    "dms": ["Gemini_Generated_Image_4mfb284mfb284mfb.png", "img_women_mom.png"],
    "fop": ["Gemini_Generated_Image_xmzqshxmzqshxmzq.png", "img_youth_cafe.png"],
    "moriak": ["Gemini_Generated_Image_n0ipvdn0ipvdn0ip.png", "img_sailor_captain.png", "img_sailor_family.png", "img_sailor_wife.png"],
    "youth": ["img_youth_cafe.png", "img_youth_library.png", "img_youth_couple.png"],
    "women": ["img_women_granny.png", "img_women_mom.png", "img_women_work.png"],
    "war": ["Gemini_Generated_Image_4mfb284mfb284mfb.png"],
    "psych": ["img_psych_money.png", "img_youth_couple.png"],
    "grawe": ["Gemini_Generated_Image_4mfb284mfb284mfb.png"],
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
    return None

def get_topic(day):
    counter = get_counter()
    idx = counter % len(TOPICS)
    return TOPICS[idx]

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

async def generate_text(topic):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = "*" + topic["hook"] + "*\n\n" + topic["text"]
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text

# ─── CALLBACK HANDLER ────────────────────────────────────────────────────────

async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "no_forward":
        # Just remove the forward buttons, keep consultation button if it was there
        msg_id = str(query.message.message_id)
        post_data = PENDING_POSTS.get(msg_id)
        if post_data and post_data["show_button"]:
            new_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 Хочу консультацію", url="https://t.me/BermanOdesa")
            ]])
            await query.edit_message_reply_markup(reply_markup=new_kb)
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

        # Build keyboard for main channel
        if post_data["show_button"] and not clean:
            main_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 Хочу консультацію", url="https://t.me/BermanOdesa")
            ]])
        else:
            main_keyboard = None

        bot = context.bot

        # Беремо АКТУАЛЬНИЙ текст з повідомлення (після можливого редагування)
        current_text = query.message.text or post_data["text"]

        # Send image first if saved
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

        # Send poll to main channel too if saved
        if post_data.get("poll_question"):
            await bot.send_poll(
                chat_id=CHANNEL_ID,
                question=post_data["poll_question"],
                options=post_data["poll_options"],
                is_anonymous=True
            )

        # Update test message: remove forward buttons, keep only consultation
        if post_data["show_button"]:
            done_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Опубліковано в основний", callback_data="done")
            ]])
        else:
            done_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Опубліковано в основний", callback_data="done")
            ]])
        await query.edit_message_reply_markup(reply_markup=done_kb)

        del PENDING_POSTS[msg_id]
        print("Forwarded to main channel: " + post_data.get("topic_name", "?"))

    if data == "done":
        await query.answer("Вже опубліковано ✅")


# ─── PUBLISH POST ─────────────────────────────────────────────────────────────

async def publish_post(bot: Bot, test_mode=False, force_image=False):
    tz = pytz.timezone(TIMEZONE)
    target = TEST_CHANNEL_ID if TEST_CHANNEL_ID else CHANNEL_ID
    now = datetime.now(tz)
    topic = get_topic(now.weekday())
    counter = get_counter()
    use_image = force_image or (counter % 2 == 0)
    inc_counter()

    print("Topic: " + topic["name"] + " | " + ("image" if use_image else "poll"))

    button_topics = ["life", "grawe", "dms", "pension", "solidarna", "cushion", "inflation"]
    show_button = any(topic["name"].startswith(t) for t in button_topics)

    consultation_btn = InlineKeyboardButton("💬 Хочу консультацію", url="https://t.me/BermanOdesa")

    try:
        text = await generate_text(topic)

        # Save image bytes for possible forwarding
        image_bytes = None
        img_path = get_topic_image(topic["name"])
        if img_path:
            print("Using local image: " + img_path)
            from PIL import Image as PILImage
            import io as _io
            pil_img = PILImage.open(img_path).convert("RGB")
            pil_img = pil_img.resize((800, 450), PILImage.LANCZOS)
            buf = _io.BytesIO()
            pil_img.save(buf, "JPEG", quality=75)
            image_bytes = buf.getvalue()
            buf.seek(0)
            await bot.send_photo(chat_id=target, photo=buf)
            print("Image sent OK")
        else:
            print("No local image for: " + topic["name"])

        # Decide poll
        will_poll = (get_counter() % 3 == 0)
        poll_question = topic.get("poll_question") if will_poll else None
        poll_options = topic.get("poll_options") if will_poll else None

        # Build keyboard
        if TEST_CHANNEL_ID:
            # Test channel: consultation + forward/skip buttons
            forward_btn = InlineKeyboardButton("✅ З кнопкою", callback_data="forward_" + topic["name"])
            forward_no_btn = InlineKeyboardButton("📨 Без кнопки", callback_data="forwardclean_" + topic["name"])
            skip_btn = InlineKeyboardButton("❌ Не пересилати", callback_data="no_forward")
            if show_button:
                keyboard = InlineKeyboardMarkup([
                    [consultation_btn],
                    [forward_btn, forward_no_btn],
                    [skip_btn]
                ])
            else:
                keyboard = InlineKeyboardMarkup([
                    [forward_btn, forward_no_btn],
                    [skip_btn]
                ])
        else:
            # No test channel — publish directly to main with only consultation
            keyboard = InlineKeyboardMarkup([[consultation_btn]]) if show_button else None

        msg = await bot.send_message(chat_id=target, text=text, parse_mode="Markdown", reply_markup=keyboard)
        print("Image sent OK")

        # Store pending post for forwarding
        if TEST_CHANNEL_ID:
            PENDING_POSTS[str(msg.message_id)] = {
                "text": text,
                "show_button": show_button,
                "topic_name": topic["name"],
                "image_bytes": image_bytes,
                "poll_question": poll_question,
                "poll_options": poll_options,
            }

        # Poll in test channel only
        if will_poll:
            await bot.send_poll(
                chat_id=target,
                question=topic.get("poll_question", "Що думаєте?"),
                options=topic.get("poll_options", ["Так", "Ні", "Ще думаю"]),
                is_anonymous=True
            )
            print("Poll sent OK")

        print("Post published OK")

    except Exception as e:
        print("Error: " + repr(e))


# ─── NEWS ─────────────────────────────────────────────────────────────────────

PENSION_KEYWORDS = [
    "пенсі", "пфу", "пенсійн", "стаж", "єсв", "накопич",
    "пенсіонер", "виплат", "пенсійного віку", "солідарн"
]
GRAWE_KEYWORDS = ["grawe", "страхуван", "накопич", "поліс", "виплат", "захист"]

def get_last_news_id():
    try:
        with open("/tmp/last_news.txt") as f:
            return f.read().strip()
    except:
        return ""

def save_last_news_id(news_id):
    with open("/tmp/last_news.txt", "w") as f:
        f.write(news_id)

async def fetch_minsoc_news():
    try:
        import re as _re
        r = requests.get("https://t.me/s/MinSocUA", timeout=15)
        if r.status_code != 200:
            return None
        posts = _re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', r.text, _re.DOTALL)
        ids = _re.findall(r'data-post="MinSocUA/(\d+)"', r.text)
        if not posts or not ids:
            return None
        last_id = get_last_news_id()
        for post_id, post_html in zip(ids, posts):
            if post_id == last_id:
                break
            text = _re.sub(r'<[^>]+>', '', post_html).strip()
            text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&#39;', "'")
            if len(text) < 50:
                continue
            if any(kw in text.lower() for kw in PENSION_KEYWORDS):
                save_last_news_id(ids[0])
                return text
        save_last_news_id(ids[0] if ids else last_id)
        return None
    except Exception as e:
        print("MinSoc error: " + repr(e))
        return None

async def fetch_channel_news(channel_name, keywords, last_file):
    try:
        import re as relib
        r = requests.get("https://t.me/s/" + channel_name, timeout=15)
        if r.status_code != 200:
            return None
        posts = relib.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', r.text, relib.DOTALL)
        ids = relib.findall(r'data-post="' + channel_name + r'/([0-9]+)"', r.text)
        if not posts or not ids:
            return None
        try:
            with open(last_file) as f:
                last_id = f.read().strip()
        except:
            last_id = ""
        for post_id, post_html in zip(ids, posts):
            if post_id == last_id:
                break
            text = relib.sub(r'<[^>]+>', '', post_html).strip()
            text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            if len(text) < 50:
                continue
            if any(kw in text.lower() for kw in keywords):
                with open(last_file, "w") as f:
                    f.write(ids[0])
                return text
        if ids:
            with open(last_file, "w") as f:
                f.write(ids[0])
        return None
    except Exception as e:
        print("Channel " + channel_name + " error: " + repr(e))
        return None

async def fetch_grawe_news():
    return await fetch_channel_news("graweinukraine", GRAWE_KEYWORDS, "/tmp/last_grawe.txt")

async def fetch_pfu_news():
    try:
        import re as relib
        r = requests.get("https://www.pfu.gov.ua/news/", timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        titles = relib.findall(r'<h[23][^>]*class="[^"]*title[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', r.text)
        if not titles:
            titles = relib.findall(r'<a[^>]*href="(/news/[^"]+)"[^>]*class="[^"]*"[^>]*>([^<]+)</a>', r.text)
        if not titles:
            return None
        PFU_LAST_FILE = "/tmp/last_pfu.txt"
        try:
            with open(PFU_LAST_FILE) as f:
                last_url = f.read().strip()
        except:
            last_url = ""
        for url, title in titles[:10]:
            title = title.strip()
            if not title or len(title) < 10:
                continue
            if url == last_url:
                break
            if any(kw in title.lower() for kw in PENSION_KEYWORDS):
                with open(PFU_LAST_FILE, "w") as f:
                    f.write(url)
                full_url = url if url.startswith("http") else "https://www.pfu.gov.ua" + url
                try:
                    article = requests.get(full_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                    text = relib.sub(r'<[^>]+>', ' ', article.text)
                    text = relib.sub(r'\s+', ' ', text).strip()
                    idx = text.find(title)
                    if idx > 0:
                        text = title + ". " + text[idx+len(title):idx+len(title)+800]
                    else:
                        text = title
                except:
                    text = title
                return text
        if titles:
            with open(PFU_LAST_FILE, "w") as f:
                f.write(titles[0][0])
        return None
    except Exception as e:
        print("PFU error: " + repr(e))
        return None

async def publish_news_post(bot: Bot, news_text, target):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (
        "Ось новина від Міністерства соціальної політики України:\n\n" + news_text +
        "\n\nПерепиши цю новину для Telegram каналу @VartaFinance фінансового консультанта. "
        "Стиль: коротко 2-3 абзаци, українською, без лапок, тон теплий. "
        "Починай з жирного хуку через *текст*. "
        "Поясни що ця новина означає для звичайної людини. "
        "Закінчи закликом написати в особисті для консультації."
    )
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    post_text = msg.content[0].text

    consultation_btn = InlineKeyboardButton("💬 Хочу консультацію", url="https://t.me/BermanOdesa")

    img_path = get_topic_image("kzpp")
    image_bytes = None
    if img_path:
        from PIL import Image as PILImage
        import io as _io
        pil_img = PILImage.open(img_path).convert("RGB")
        pil_img = pil_img.resize((800, 450), PILImage.LANCZOS)
        buf = _io.BytesIO()
        pil_img.save(buf, "JPEG", quality=75)
        image_bytes = buf.getvalue()
        buf.seek(0)
        await bot.send_photo(chat_id=target, photo=buf)

    if TEST_CHANNEL_ID:
        forward_btn = InlineKeyboardButton("✅ З кнопкою", callback_data="forward_news")
        forward_no_btn = InlineKeyboardButton("📨 Без кнопки", callback_data="forwardclean_news")
        skip_btn = InlineKeyboardButton("❌ Не пересилати", callback_data="no_forward")
        keyboard = InlineKeyboardMarkup([
            [consultation_btn],
            [forward_btn, forward_no_btn],
            [skip_btn]
        ])
    else:
        keyboard = InlineKeyboardMarkup([[consultation_btn]])

    msg_out = await bot.send_message(chat_id=target, text=post_text, parse_mode="Markdown", reply_markup=keyboard)

    if TEST_CHANNEL_ID:
        PENDING_POSTS[str(msg_out.message_id)] = {
            "text": post_text,
            "show_button": True,
            "topic_name": "news",
            "image_bytes": image_bytes,
            "poll_question": None,
            "poll_options": None,
        }

    print("News post published OK")
    inc_counter()

async def check_and_publish_news(bot: Bot):
    target = TEST_CHANNEL_ID if TEST_CHANNEL_ID else CHANNEL_ID
    sources = [
        ("MinSocUA", fetch_minsoc_news),
        ("GRAWE", fetch_grawe_news),
        ("PFU", fetch_pfu_news),
    ]
    for source_name, fetch_func in sources:
        print("Checking " + source_name + "...")
        try:
            news = await fetch_func()
            if news:
                await publish_news_post(bot, news, target)
                print("Published news from " + source_name)
                return
            else:
                print("No new news from " + source_name)
        except Exception as e:
            print("Error checking " + source_name + ": " + repr(e))
    print("No new news from any source today")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    print("VartaFinance Bot started!")

    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connection_pool_size=8, read_timeout=60, write_timeout=60, connect_timeout=30)

    # Build Application (handles polling + callbacks)
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CallbackQueryHandler(handle_forward))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    bot = app.bot

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Regular posts Mon/Wed/Fri at 10:00
    scheduler.add_job(
        publish_post,
        CronTrigger(day_of_week=SCHEDULE_DAYS, hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone=TIMEZONE),
        kwargs={"bot": bot}
    )

    # News check daily at 21:00
    scheduler.add_job(
        check_and_publish_news,
        CronTrigger(hour=21, minute=0, timezone=TIMEZONE),
        kwargs={"bot": bot}
    )

    scheduler.start()

    print("Test post in 5 sec...")
    await asyncio.sleep(5)
    await publish_post(bot=bot, test_mode=False, force_image=True)
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
