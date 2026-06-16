import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import os
import time
from datetime import timedelta

TOKEN = "MTUxNjQ4MTQ0NDYyMzY4MzY3NQ.G4atkW.guak6Zoymi-jY_8KOPgmtjT80qx3mfcjHCZsKk"
GUILD_ID = 1514354744435675418
guild_obj = discord.Object(id=GUILD_ID)

ADMIN_ROLE = 1516503885554913462
LEVELUP_CHANNEL = 1516272773415047228
SONG_FOLDER = "songs"
XP_COOLDOWN = 30

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ✅ FORCE OPUS LOAD (fix 4017)
import discord.opus
if not discord.opus.is_loaded():
    try:
        discord.opus.load_opus("libopus.so.0")
    except:
        pass

xp_data = {}
cooldowns = {}
voice_clients = {}
song_queues = {}

# ---------------- READY ---------------- #

@bot.event
async def on_ready():
    await bot.tree.sync(guild=guild_obj)
    print(f"{bot.user} ready.")

# ---------------- ADMIN CHECK ---------------- #

def is_admin(inter):
    return any(r.id == ADMIN_ROLE for r in inter.user.roles)

# ---------------- XP SYSTEM ---------------- #

def xp_needed(level):
    return 30 * level * level + 70 * level

def calc_level(xp):
    lvl = 0
    while xp >= xp_needed(lvl + 1):
        lvl += 1
    return lvl

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    now = time.time()

    if uid not in cooldowns or now - cooldowns[uid] > XP_COOLDOWN:
        cooldowns[uid] = now
        xp_data[uid] = xp_data.get(uid, 0) + random.randint(15, 25)

    await bot.process_commands(message)

# ---------------- XP COMMANDS ---------------- #

@bot.tree.command(description="Set a user's XP.", guild=guild_obj)
async def setxp(inter: discord.Interaction, user: discord.Member, amount: int):
    if not is_admin(inter):
        return await inter.response.send_message("No permission.", ephemeral=True)
    xp_data[user.id] = amount
    await inter.response.send_message("XP set.")

@bot.tree.command(description="Add XP to a user.", guild=guild_obj)
async def addxp(inter: discord.Interaction, user: discord.Member, amount: int):
    if not is_admin(inter):
        return await inter.response.send_message("No permission.", ephemeral=True)
    xp_data[user.id] = xp_data.get(user.id, 0) + amount
    await inter.response.send_message("XP added.")

@bot.tree.command(description="Remove XP from a user.", guild=guild_obj)
async def removexp(inter: discord.Interaction, user: discord.Member, amount: int):
    if not is_admin(inter):
        return await inter.response.send_message("No permission.", ephemeral=True)
    xp_data[user.id] = max(0, xp_data.get(user.id, 0) - amount)
    await inter.response.send_message("XP removed.")

# ---------------- ADMIN COMMANDS ---------------- #

@bot.tree.command(description="Ban a user.", guild=guild_obj)
async def ban(inter: discord.Interaction, user: discord.Member):
    if not is_admin(inter):
        return await inter.response.send_message("No permission.", ephemeral=True)
    await user.ban()
    await inter.response.send_message("User banned.")

@bot.tree.command(description="Kick a user.", guild=guild_obj)
async def kick(inter: discord.Interaction, user: discord.Member):
    if not is_admin(inter):
        return await inter.response.send_message("No permission.", ephemeral=True)
    await user.kick()
    await inter.response.send_message("User kicked.")

@bot.tree.command(description="Timeout a user.", guild=guild_obj)
async def timeout(inter: discord.Interaction, user: discord.Member, minutes: int):
    if not is_admin(inter):
        return await inter.response.send_message("No permission.", ephemeral=True)
    await user.timeout(timedelta(minutes=minutes))
    await inter.response.send_message("User timed out.")

# ---------------- IMPROVE ---------------- #

@bot.tree.command(description="Get a looks improvement tip.", guild=guild_obj)
async def improve(inter: discord.Interaction):
    await inter.response.defer()
    if not os.path.exists("improve.txt"):
        return await inter.followup.send("improve.txt missing.")
    with open("improve.txt") as f:
        tips = [x.strip() for x in f if x.strip()]
    await inter.followup.send(random.choice(tips))

# ---------------- MUSIC ---------------- #

def get_songs():
    if not os.path.exists(SONG_FOLDER):
        os.makedirs(SONG_FOLDER)
    return [f for f in os.listdir(SONG_FOLDER) if f.endswith(".mp3")]

async def play_next(guild_id):
    vc = voice_clients.get(guild_id)
    queue = song_queues.get(guild_id, [])

    if not queue:
        if vc:
            await vc.disconnect()
        return

    song = queue.pop(0)
    source = discord.FFmpegPCMAudio(f"{SONG_FOLDER}/{song}")

    def after_play(err):
        fut = play_next(guild_id)
        discord.run_coroutine_threadsafe(fut, bot.loop)

    vc.play(source, after=after_play)

@bot.tree.command(description="Play a song in VC.", guild=guild_obj)
async def singasong(inter: discord.Interaction, song: str):
    await inter.response.defer()

    songs = get_songs()
    if song not in songs:
        return await inter.followup.send("Song not found.")

    if not inter.user.voice:
        return await inter.followup.send("Join VC first.")

    channel = inter.user.voice.channel
    vc = voice_clients.get(inter.guild.id)

    if not vc:
        vc = await channel.connect()
        voice_clients[inter.guild.id] = vc

    if vc.is_playing():
        song_queues.setdefault(inter.guild.id, []).append(song)
        return await inter.followup.send(f"Added **{song}** to queue.")

    source = discord.FFmpegPCMAudio(f"{SONG_FOLDER}/{song}")

    def after_play(err):
        fut = play_next(inter.guild.id)
        discord.run_coroutine_threadsafe(fut, bot.loop)

    vc.play(source, after=after_play)
    await inter.followup.send(f"Now playing **{song}**")

@singasong.autocomplete("song")
async def autocomplete_song(inter: discord.Interaction, current: str):
    songs = get_songs()
    return [
        app_commands.Choice(name=s, value=s)
        for s in songs if current.lower() in s.lower()
    ][:25]

@bot.tree.command(description="Stop music.", guild=guild_obj)
async def stopsong(inter: discord.Interaction):
    vc = voice_clients.get(inter.guild.id)
    if not vc:
        return await inter.response.send_message("Nothing playing.", ephemeral=True)
    song_queues[inter.guild.id] = []
    vc.stop()
    await vc.disconnect()
    await inter.response.send_message("Stopped music.")

bot.run(TOKEN)
