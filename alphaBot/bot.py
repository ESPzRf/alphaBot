import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # опционально, для быстрой синхронизации команд

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")

intents = discord.Intents.default()
intents.members = True  # нужно для кика/бана/таймаута и получения member-объектов


class ModBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        await self.load_extension("cogs.moderation")

        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Синхронизировано %d команд(ы) для сервера %s", len(synced), GUILD_ID)
        else:
            synced = await self.tree.sync()
            log.info("Синхронизировано %d команд(ы) глобально", len(synced))

    async def on_ready(self):
        log.info("Бот запущен как %s (ID: %s)", self.user, self.user.id)


async def main():
    if not TOKEN:
        raise SystemExit(
            "Не найден DISCORD_TOKEN. Скопируй .env.example в .env и впиши туда токен бота."
        )

    bot = ModBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
