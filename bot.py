import os
import asyncio
import random
import io
from datetime import datetime
import anthropic
import openai
import requests
import re
from PIL import Image, ImageDraw, ImageFont
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@VartaFinance")
TEST_CHANNEL_ID = os.getenv("TEST_CHANNEL_ID", "")
MINSOC_CHANNEL = "@MinSocUA"

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
        # Init based on current hour to avoid repeating same post after restart
        import time
        val = int(time.time()) % 100
        with open(COUNTER_FILE, "w") as f:
            f.write(str(val))
        return val

def inc_counter():
    c = get_counter() + 1
    with open(COUNTER_FILE, "w") as f:
        f.write(str(c))

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
    import os as _os
    W, H = 1080, 1080
    PHOTO_Y = 160
    PHOTO_H = 760

    # Load Canva template
    template_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "template.png")
    if _os.path.exists(template_path):
        img = Image.open(template_path).convert("RGB").resize((W, H))
        print("Template loaded OK")
    else:
        img = Image.new("RGB", (W, H), DARK_BLUE)
        print("Template not found, using fallback")

    # Paste AI photo in middle area
    if photo_url:
        try:
            r = requests.get(photo_url, timeout=20)
            photo = Image.open(io.BytesIO(r.content)).convert("RGB")
            photo = photo.resize((W, PHOTO_H), Image.LANCZOS)
            img.paste(photo, (0, PHOTO_Y))
            print("Photo pasted OK")
        except Exception as e:
            print("photo err: " + str(e))

    # Redraw top brand bar over photo (so brand stays visible)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 155], fill=DARK_BLUE)
    draw.rectangle([0, 0, W, 8], fill=GOLD)
    draw.rectangle([0, 145, W, 155], fill=GOLD)

    # Redraw bottom bar
    draw.rectangle([0, H-95, W, H], fill=DARK_BLUE)
    draw.rectangle([0, H-97, W, H-91], fill=GOLD)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

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

async def generate_photo(prompt, retries=2):
    import time
    client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=120)
    for attempt in range(retries):
        try:
            resp = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1
            )
            return resp.data[0].url
        except Exception as e:
            print("Photo attempt " + str(attempt+1) + " failed: " + str(e))
            if attempt < retries - 1:
                time.sleep(5)
    return None

async def get_minsoc_news(bot):
    """Отримати останні новини з @MinSocUA через web preview"""
    try:
        url = "https://t.me/s/MinSocUA"
        r = requests.get(url, timeout=10)
        # Extract last post text
        posts = re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', r.text, re.DOTALL)
        if posts:
            # Clean HTML tags
            text = re.sub(r'<[^>]+>', '', posts[-1]).strip()
            return text[:500] if len(text) > 500 else text
    except Exception as e:
        print("MinSoc parse error: " + str(e))
    return None

async def publish_post(test_mode=False):
    target_channel = TEST_CHANNEL_ID if (test_mode and TEST_CHANNEL_ID) else CHANNEL_ID
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connection_pool_size=8, read_timeout=60, write_timeout=60, connect_timeout=30)
    bot = Bot(token=TELEGRAM_TOKEN, request=request)
    tz = pytz.timezone(TIMEZONE)
    target = TEST_CHANNEL_ID if (test_mode and TEST_CHANNEL_ID) else CHANNEL_ID
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
            image_buf = create_varta_image(topic["hook"], photo_url)
            await bot.send_photo(chat_id=target, photo=image_buf)
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Хочу консультацію", url="https://t.me/BermanOdesa")]])
            await bot.send_message(chat_id=target, text=text, parse_mode="Markdown", reply_markup=keyboard)
            print("Posted with image OK")
        else:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Хочу консультацію", url="https://t.me/BermanOdesa")]])
            await bot.send_message(chat_id=target, text=text, parse_mode="Markdown", reply_markup=keyboard)
            await bot.send_poll(
                chat_id=target,
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
    await publish_post(test_mode=True)
    print("Running...")
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
