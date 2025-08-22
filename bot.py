# -*- coding: utf-8 -*-
import os, json, asyncio, openai
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = "scores.json"
QUIZ_TIMEOUT = 20
POINTS = {"Easy":5, "Medium":10, "Hard":15}
CATEGORIES = ["أنمي","Free Fire","Gaming","عامة"]

# مفتاح OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# تحميل وحفظ النقاط
def load_scores():
    if not os.path.exists(DATA_FILE): return {}
    try: return json.load(open(DATA_FILE,"r",encoding="utf-8"))
    except: return {}
def save_scores(scores): json.dump(scores, open(DATA_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
def add_points(uid, pts): scores=load_scores(); scores[str(uid)] = scores.get(str(uid),0)+pts; save_scores(scores)
def top_scores(n=10): items=[(int(uid),pts) for uid,pts in load_scores().items()]; items.sort(key=lambda x:x[1],reverse=True); return items[:n]

# View و Buttons
class ChoiceView(discord.ui.View):
    def __init__(self, choices, correct):
        super().__init__(timeout=QUIZ_TIMEOUT)
        self.correct = correct
        self.answered = False
        for i,c in enumerate(choices): self.add_item(ChoiceButton(label=c,i=i))
class ChoiceButton(discord.ui.Button):
    def __init__(self,label,i): super().__init__(label=label,style=discord.ButtonStyle.secondary); self.i=i
    async def callback(self, interaction): 
        view:ChoiceView=self.view
        if view.answered: await interaction.response.send_message("❌ تمّت الإجابة!",ephemeral=True); return
        view.answered=True
        for item in view.children: item.disabled=True
        await interaction.response.edit_message(view=view)
        self.view.result = self.i==view.correct

# Intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ {bot.user} جاهز ويشتغل! {len(synced)} أوامر مسجلة")
    except Exception as e:
        print(e)

# توليد الأسئلة باستخدام AI (سريع)
async def generate_questions(category, difficulty, number=5):
    prompt = f"""
    اصنع لي {number} أسئلة قصيرة حول {category} بمستوى صعوبة {difficulty}.
    كل سؤال يجب أن يكون مع 4 خيارات والإشارة للخيار الصحيح (0 هو الخيار الأول).
    أرجعها على شكل JSON:
    [
        {{'نص':'','خيارات':[],'صح':0,'صعوبة':''}}
    ]
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # أسرع من GPT-4
        messages=[{"role":"user","content":prompt}],
        max_tokens=300,
        temperature=0.7
    )
    content = response.choices[0].message.content
    try: return json.loads(content)
    except:
        return [{"نص":"خطأ في توليد الأسئلة","خيارات":["خطأ"],"صح":0,"صعوبة":difficulty}]

# لوحة النتائج
@bot.tree.command(name="لوحة_النتائج",description="عرض أفضل اللاعبين")
async def leaderboard(inter:discord.Interaction):
    scores = top_scores(10)
    if not scores: await inter.response.send_message("لا توجد نتائج بعد!"); return
    embed=discord.Embed(title="🏆 لوحة النتائج",color=discord.Color.green())
    for i,(uid,pts) in enumerate(scores,1):
        user = await bot.fetch_user(uid)
        embed.add_field(name=f"{i}. {user.name}",value=f"النقاط: {pts}",inline=False)
    await inter.response.send_message(embed=embed)

# أمر المسابقة
@bot.tree.command(name="مسابقة",description="ابدأ مسابقة")
@app_commands.choices(
    فئة=[app_commands.Choice(name=c,value=c) for c in CATEGORIES]
)
@app_commands.choices(
    صعوبة=[app_commands.Choice(name=s,value=s) for s in POINTS.keys()]
)
async def quiz(
    inter: discord.Interaction,
    فئة: app_commands.Choice[str],
    صعوبة: app_commands.Choice[str],  # المستخدم يختار
    عدد: int = 5
):
    await inter.response.send_message(f"⏳ يتم توليد الأسئلة الجديدة...")
    questions_pool = await generate_questions(fئة.value, صعوبة.value, عدد)
    
    total_points=0
    for n,q in enumerate(questions_pool,1):
        view=ChoiceView(q["خيارات"],q["صح"])
        msg = await inter.followup.send(f"❓ {q['نص']}", view=view)
        timeout=0
        while not hasattr(view,"result"):
            await asyncio.sleep(0.5)
            timeout+=0.5
            if timeout>QUIZ_TIMEOUT: view.result=False; break
        if view.result:
            pts = POINTS[q["صعوبة"]]
            total_points+=pts
            add_points(inter.user.id,pts)
        else:
            await inter.followup.send(f"❌ إجابة خاطئة! المسابقة انتهت. مجموع نقاطك: {total_points}")
            break

    embed=discord.Embed(title="🎉 مبروك! لقد أنهيت المسابقة!",description=f"{inter.user.mention} حصل على {total_points} نقاط",color=discord.Color.gold())
    embed.set_thumbnail(url=inter.user.avatar.url)
    await inter.followup.send(embed=embed)

# تشغيل البوت
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
