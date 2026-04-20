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
SYSTEM_PROMPT = (
"Ty — kontent-menedzher dlya Telegram-kanalu @VartaFinance finansovoho konsultanta Oksany
"Vona spetsializuyetsya na strakhovanni ta pensiynomu planuvanni, pratsyuye zi strakhovoy
"PRAVYLA POSTIV: "
"Mova: vyklyuchno ukrayinska, bez surzhyku. "
"Ton: druzhni i tyoplyy, yak porada vid blyzkoyi lyudyny. "
"Dovzhyna: 150-280 sliv (optymalno dlya Telegram). "
"Obovyazkovo zgaduvaty realni normy zakonodavstva Ukrayiny (nazva zakonu, nomer statti ab
"Ne pysaty zahalni frazy — tilky konkretyka. "
"Zakinchennya: abo zapytannya do chytachiv, abo myakyi CTA (napysaty v osobysti / zapysat
"Vykorystovuvaty emodzhi orhanichno (3-6 na post), ne spamyty nymy. "
"NE pysaty kheshtehy. Pidpys ne potriben."
)
TOPIC_PENSION = (
"Napyshi osvitniy post pro pensiy ne nakopychennya v Ukrayini. "
"Temy: nederzhavni pensiyni fondy (NPF), indyvidualni pensiyni rakhunky, prohramy GRAWE U
"Zakonodavstvo: Zakon N 1057-IV Pro nederzhavne pensiy ne zabezpechennya, "
"st. 166.3.3 PKU (podatkova znyzhka na vnesky do NPF). "
"Aktsent: serednya pensiya v Ukrayini 3500-4000 hrn menshe prozhytkovoho minimumu. "
"Osobysti nakopychennya yedynyy vykhid. "
"Plavno pidvody do dumky shcho treba pochynaty nakopychuvaty samostiyno."
)
TOPIC_STAZH = (
"Napyshi post pro trudovyy stazh v Ukrayini — shcho zarakhovuyetsya, yak pidtverdzhuyetsy
"Zakonodavstvo: KZpP Ukrayiny, Zakon N 1058-IV st. 24-26 (strakhovyy stazh), "
"osoblyvosti dlya FOP cherez YeSV. "
"Aktsent: bez minimalnoho strakhovoho stazhu 15 rokiv pensiya ne pryznachayetsya vzahali.
"Korysna porada dlya samozaynyatykh, FOP, moryakiv, IT-spetsialistiv."
)
TOPIC_SOLIDARNA = (
"Napyshi zasterezhlyvyy post pro solidarnu derzhavnu pensiyu v Ukrayini. "
"Zakonodavstvo: Zakon N 1058-IV, st. 27 (umovy pryznachennya pensiyi), byudzhet PFU. "
"Fakty: demohrafichna kryza — na 10 pensivoneriv lyshe 6 platnykiv YeSV. Systema defitsyt
"Realna pensiya pokryvaye blyzko 30 vidsotky vid serednoyi zarplaty. "
"Pidvody do vysnovku: derzhava ne vstygne, treba dbaty samomu."
)
TOPIC_ETRУДОВА = (
"Napyshi korysnyy post pro elektronnu trudovu knyzhku e-trudovu v Ukrayini. "
"Zakonodavstvo: Zakon N 1217-IX vid 05.02.2021, postanova KMU N 509 vid 27.05.2021. "
"Yak pereviryt sviy stazh v Diyi abo na sayti PFU. "
"Shcho robyty yakshcho ye pomylky v zapysakh — praktychna porada."
)
TOPIC_DMS = (
"Napyshi post pro dobrovilne medychne strakhuvannya DMS v Ukrayini. "
"Zakonodavstvo: Zakon Pro strakhuvannya N 85/96-VR, st. 142.1 PKU pilhy dlya robotodavtsi
"Aktsent: GRAWE Ukraine — avstriyskyy kapital, ponad 25 rokiv na rynku, litsenziya "V umovakh voyennoho stanu dostup do yakisnoy medytsyny — pytannya zakhystu simyi."
NBU. "
)
TOPIC_LIFE = (
"Napyshi post pro strakhuvannya zhyttya v Ukrayini yak instrument zakhystu i nakopychenny
"Zakonodavstvo: Zakon Pro strakhuvannya N 85/96-VR, st. 166.3.5 PKU "
"podatkova znyzhka do 2690 hrn na misyats. "
"GRAWE Ukraine — poyednuye zakhyst plus nakopychennya plus podatkovu znyzhku. "
"Osoblivo aktualno dlya FOP, moryakiv, IT — u koho nemaye sotsialnykh harantiy vid derzha
)
TOPIC_KZPP = (
"Napyshi informatsiynyy post pro zminy v trudovomu zakonodavstvi Ukrayiny. "
"Zakonodavstvo: KZpP Ukrayiny, Zakon N 2136-IX vid 15.03.2022 prats v umovakh voyennoho s
"Yak zminy vplyvayut na strakhovyy stazh i maybutniu pensiyu. "
"Korysno znaty kozhnomu nayanomu pratsivnyku i FOP."
)
TOPICS = [
{"name": "pension", "prompt": TOPIC_PENSION},
{"name": "stazh", "prompt": TOPIC_STAZH},
{"name": "solidarna", "prompt": TOPIC_SOLIDARNA},
{"name": "etrudova", "prompt": TOPIC_ETRУДОВА},
{"name": "dms", "prompt": TOPIC_DMS},
{"name": "life", "prompt": TOPIC_LIFE},
{"name": "kzpp", "prompt": TOPIC_KZPP},
]
def get_next_topic(day_of_week):
day_map = {0: [0, 4, 5], 2: [1, 2, 3], 4: [4, 5, 6]}
indices = day_map.get(day_of_week, list(range(len(TOPICS))))
return random.choice([TOPICS[i] for i in indices])
async def generate_post(topic):
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
message = client.messages.create(
model="claude-opus-4-5",
max_tokens=1000,
system=SYSTEM_PROMPT,
messages=[{"role": "user", "content": topic["prompt"]}]
)
return message.content[0].text
async def publish_post():
bot = Bot(token=TELEGRAM_TOKEN)
kyiv_tz = pytz.timezone(TIMEZONE)
now = datetime.now(kyiv_tz)
day_of_week = now.weekday()
print("Generating post for topic...")
topic = get_next_topic(day_of_week)
print("Topic: " + topic["name"])
try:
post_text = await generate_post(topic)
await bot.send_message(
chat_id=CHANNEL_ID,
text=post_text,
parse_mode=None
)
print("OK! Post published! Chars: " + str(len(post_text)))
except Exception as e:
print("ERROR: " + str(e))
async def main():
print("VartaFinance Bot started!")
print("Channel: " + CHANNEL_ID)
print("Schedule: days " + SCHEDULE_DAYS + " at " + str(SCHEDULE_HOUR) + ":00 Kyiv")
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
print("Test post in 5 seconds...")
await asyncio.sleep(5)
await publish_post()
print("Bot running. Waiting for schedule...")
try:
while True:
await asyncio.sleep(60)
except (KeyboardInterrupt, SystemExit):
scheduler.shutdown()
print("Bot stopped.")
if __name__ == "__main__":
asyncio.run(main())
