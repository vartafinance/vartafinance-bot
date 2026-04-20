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
SYSTEM_PROMPT = "\n".join([
"Ty kontent-menedzher dlya Telegram-kanalu @VartaFinance finansovoho konsultanta Oksany z
"Vona spetsializuyetsya na strakhovanni ta pensiynomu planuvanni z GRAWE Ukraine.",
"PRAVYLA:",
"- Mova: ukrayinska",
"- Ton: druzhny i tyoply",
"- Dovzhyna: 150-280 sliv",
"- Zgaduvaty zakony Ukrayiny z nomeramy",
"- Zakinchennya: zapytannya abo CTA",
"- Emodzhi: 3-6 na post",
"- Bez kheshteyhiv, bez pidpysu",
])
TOPICS = [
{
"name": "pension",
"day": [0],
"text": "\n".join([
"Napyshi ukrayinskoyu movoyu osvitniy post pro pensiy ne nakopychennya.",
"Temy: NPF nederzhavni pensiyni fondy, GRAWE Ukraine programy.",
"Zakony: Zakon 1057-IV pro NPF, stattya 166.3.3 PKU podatkova znyzhka.",
"Fakt: pensiya v Ukrayini 3500 hrn menshe minimumu. Treba kopychyty samostiyno.",
"Zavershyy pryaznym zaklykom zapysatysya na konsultatsiyu.",
])
},
{
},
{
},
{
},
{
},
{
"name": "stazh",
"day": [2],
"text": "\n".join([
"Napyshi ukrayinskoyu movoyu post pro trudovyy stazh.",
"Zakony: KZpP Ukrayiny, Zakon 1058-IV statti 24-26 pro strakhovyy stazh.",
"Fakt: bez 15 rokiv stazhu pensiya ne pryznachayetsya.",
"Porada dlya FOP, moryakiv, IT spetsialistiv.",
"Zavershyy zapytannyam do chytachiv.",
])
"name": "solidarna",
"day": [2],
"text": "\n".join([
"Napyshi ukrayinskoyu movoyu post pro derzhavnu pensiyu.",
"Zakony: Zakon 1058-IV stattya 27 umovy pryznachennya pensiyi.",
"Fakt: na 10 pensivoneriv lyshe 6 platnykiv. Pensiya lyshe 30 vidsotky zarplaty."
"Vysnovok: treba kopychyty samostiyno.",
"Zavershyy zapytannyam.",
])
"name": "etrudova",
"day": [2],
"text": "\n".join([
"Napyshi ukrayinskoyu movoyu post pro elektronnu trudovu knyzhku.",
"Zakony: Zakon 1217-IX vid 2021 roku, postanova KMU 509.",
"Yak pereviryt stazh v Diyi abo na sayti PFU.",
"Shcho robyty pry pomylkakh u zapysakh.",
"Zavershyy poradoyu.",
])
"name": "dms",
"day": [4],
"text": "\n".join([
"Napyshi ukrayinskoyu movoyu post pro DMS dobrovilne medychne strakhuvannya.",
"Zakony: Zakon pro strakhuvannya 85/96-VR, stattya 142.1 PKU pilhy.",
"GRAWE Ukraine: 25 rokiv na rynku, litsenziya NBU.",
"Aktsent na zakhysti simyi pid chas viyni.",
"Zavershyy pryaznym zaklykom.",
])
"name": "life",
"day": [4],
"text": "\n".join([
"Napyshi ukrayinskoyu movoyu post pro strakhuvannya zhyttya.",
"Zakony: Zakon 85/96-VR, stattya 166.3.5 PKU podatkova znyzhka 2690 hrn na "GRAWE Ukraine: zakhyst plus nakopychennya plus podatkova znyzhka razom.",
"Dlya FOP moryakiv IT bez derzhavnykh harantiy.",
"Zavershyy zaklykom na konsultatsiyu.",
misyat
])
},
{
"name": "kzpp",
"day": [0],
"text": "\n".join([
"Napyshi ukrayinskoyu movoyu post pro zminy v trudovomu zakonodavstvi.",
"Zakony: KZpP, Zakon 2136-IX vid 2022 pro pratsyu pid chas viynyy, Zakon 3720-IX.
"Yak zminy vplyvayut na stazh i pensiyu.",
"Dlya naymanykh pratsivnykiv i FOP.",
"Zavershyy zapytannyam.",
])
},
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
print("Posted OK, chars: " + str(len(text)))
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
print("Running, waiting for schedule...")
try:
while True:
await asyncio.sleep(60)
except (KeyboardInterrupt, SystemExit):
scheduler.shutdown()
if __name__ == "__main__":
asyncio.run(main())
