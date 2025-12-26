# bot.py
import discord
from discord.ext import commands
import asyncio
import os
from config import TOKEN, PREFIX

intents = discord.Intents.default()
intents.message_content = True          # обязательно для чтения текста
intents.members = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")
    print(f"ID: {bot.user.id}")
    print("------")

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and filename != "__init__.py":
            await bot.load_extension(f"cogs.{filename[:-3]}")

async def main():
    await load_cogs()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())


# Запуск бота
bot.run("123456789012345678")