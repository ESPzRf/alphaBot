import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("bot.moderation")

# Готовый список таймаутов: (подпись в Discord, timedelta)
TIMEOUT_CHOICES = [
    app_commands.Choice(name="60 секунд", value="60"),
    app_commands.Choice(name="5 минут", value="300"),
    app_commands.Choice(name="10 минут", value="600"),
    app_commands.Choice(name="1 час", value="3600"),
    app_commands.Choice(name="1 день", value="86400"),
    app_commands.Choice(name="1 неделя", value="604800"),
]


def format_timedelta(seconds: int) -> str:
    td = timedelta(seconds=seconds)
    days, rem = divmod(int(td.total_seconds()), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} дн.")
    if hours:
        parts.append(f"{hours} ч.")
    if minutes:
        parts.append(f"{minutes} мин.")
    if secs and not days and not hours:
        parts.append(f"{secs} сек.")
    return " ".join(parts) or "0 сек."


class Moderation(commands.Cog):
    """Базовые команды модерации: таймаут, кик, бан."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- общие проверки ----------

    @staticmethod
    def _bot_can_act_on(bot_member: discord.Member, target: discord.Member) -> bool:
        """Проверка иерархии ролей: бот должен быть выше цели."""
        return bot_member.top_role > target.top_role

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            msg = "У тебя недостаточно прав для этой команды."
        elif isinstance(error, app_commands.BotMissingPermissions):
            msg = "У бота недостаточно прав для выполнения этого действия."
        else:
            msg = f"Произошла ошибка: {error}"
            log.exception("Ошибка в команде модерации", exc_info=error)

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    # ---------- /timeout ----------

    @app_commands.command(name="timeout", description="Выдать пользователю таймаут")
    @app_commands.describe(
        member="Кого таймаутить",
        duration="Длительность таймаута",
        reason="Причина (необязательно)",
    )
    @app_commands.choices(duration=TIMEOUT_CHOICES)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: app_commands.Choice[str],
        reason: str = "Причина не указана",
    ):
        seconds = int(duration.value)

        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "Нельзя выдать таймаут самому себе.", ephemeral=True
            )
            return

        if member.bot:
            await interaction.response.send_message(
                "Нельзя выдать таймаут боту.", ephemeral=True
            )
            return

        bot_member = interaction.guild.me
        if not self._bot_can_act_on(bot_member, member):
            await interaction.response.send_message(
                "Моя роль ниже роли этого пользователя (или равна ей) — не могу выдать таймаут.",
                ephemeral=True,
            )
            return

        if (
            isinstance(interaction.user, discord.Member)
            and member.top_role >= interaction.user.top_role
            and interaction.user.id != interaction.guild.owner_id
        ):
            await interaction.response.send_message(
                "Нельзя выдать таймаут пользователю с ролью выше или равной твоей.",
                ephemeral=True,
            )
            return

        try:
            await member.timeout(timedelta(seconds=seconds), reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "Не хватает прав для выдачи таймаута этому пользователю.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⏱️ Таймаут выдан",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Пользователь", value=member.mention, inline=True)
        embed.add_field(name="Длительность", value=duration.name, inline=True)
        embed.add_field(name="Модератор", value=interaction.user.mention, inline=True)
        embed.add_field(name="Причина", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)

        try:
            await member.send(
                f"Тебе выдан таймаут на сервере **{interaction.guild.name}** "
                f"на {duration.name}.\nПричина: {reason}"
            )
        except discord.Forbidden:
            pass  # у пользователя закрыты личные сообщения

    # ---------- /kick ----------

    @app_commands.command(name="kick", description="Кикнуть пользователя с сервера")
    @app_commands.describe(member="Кого кикнуть", reason="Причина (необязательно)")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Причина не указана",
    ):
        if member.id == interaction.user.id:
            await interaction.response.send_message("Нельзя кикнуть самого себя.", ephemeral=True)
            return

        bot_member = interaction.guild.me
        if not self._bot_can_act_on(bot_member, member):
            await interaction.response.send_message(
                "Моя роль ниже роли этого пользователя (или равна ей) — не могу кикнуть.",
                ephemeral=True,
            )
            return

        if (
            isinstance(interaction.user, discord.Member)
            and member.top_role >= interaction.user.top_role
            and interaction.user.id != interaction.guild.owner_id
        ):
            await interaction.response.send_message(
                "Нельзя кикнуть пользователя с ролью выше или равной твоей.", ephemeral=True
            )
            return

        try:
            await member.send(
                f"Тебя кикнули с сервера **{interaction.guild.name}**.\nПричина: {reason}"
            )
        except discord.Forbidden:
            pass

        try:
            await member.kick(reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "Не хватает прав для кика этого пользователя.", ephemeral=True
            )
            return

        embed = discord.Embed(title="👢 Пользователь кикнут", color=discord.Color.red())
        embed.add_field(name="Пользователь", value=f"{member} ({member.id})", inline=True)
        embed.add_field(name="Модератор", value=interaction.user.mention, inline=True)
        embed.add_field(name="Причина", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)

    # ---------- /ban ----------

    @app_commands.command(name="ban", description="Забанить пользователя на сервере")
    @app_commands.describe(
        member="Кого забанить",
        reason="Причина (необязательно)",
        delete_message_days="Удалить сообщения за последние N дней (0-7)",
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Причина не указана",
        delete_message_days: app_commands.Range[int, 0, 7] = 0,
    ):
        if member.id == interaction.user.id:
            await interaction.response.send_message("Нельзя забанить самого себя.", ephemeral=True)
            return

        bot_member = interaction.guild.me
        if not self._bot_can_act_on(bot_member, member):
            await interaction.response.send_message(
                "Моя роль ниже роли этого пользователя (или равна ей) — не могу забанить.",
                ephemeral=True,
            )
            return

        if (
            isinstance(interaction.user, discord.Member)
            and member.top_role >= interaction.user.top_role
            and interaction.user.id != interaction.guild.owner_id
        ):
            await interaction.response.send_message(
                "Нельзя забанить пользователя с ролью выше или равной твоей.", ephemeral=True
            )
            return

        try:
            await member.send(
                f"Тебя забанили на сервере **{interaction.guild.name}**.\nПричина: {reason}"
            )
        except discord.Forbidden:
            pass

        try:
            await member.ban(
                reason=f"{interaction.user}: {reason}",
                delete_message_seconds=delete_message_days * 86400,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Не хватает прав для бана этого пользователя.", ephemeral=True
            )
            return

        embed = discord.Embed(title="🔨 Пользователь забанен", color=discord.Color.dark_red())
        embed.add_field(name="Пользователь", value=f"{member} ({member.id})", inline=True)
        embed.add_field(name="Модератор", value=interaction.user.mention, inline=True)
        embed.add_field(name="Причина", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)

    # ---------- /unban (бонус, пригодится вместе с баном) ----------

    @app_commands.command(name="unban", description="Разбанить пользователя по ID")
    @app_commands.describe(user_id="ID пользователя для разбана", reason="Причина (необязательно)")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "Причина не указана",
    ):
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message("ID должен быть числом.", ephemeral=True)
            return

        try:
            user = discord.Object(id=uid)
            await interaction.guild.unban(user, reason=f"{interaction.user}: {reason}")
        except discord.NotFound:
            await interaction.response.send_message(
                "Пользователь с таким ID не забанен.", ephemeral=True
            )
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "Не хватает прав для разбана.", ephemeral=True
            )
            return

        embed = discord.Embed(title="✅ Пользователь разбанен", color=discord.Color.green())
        embed.add_field(name="ID", value=str(uid), inline=True)
        embed.add_field(name="Модератор", value=interaction.user.mention, inline=True)
        embed.add_field(name="Причина", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)

    # ---------- /remove_timeout (бонус, пригодится вместе с таймаутом) ----------

    @app_commands.command(name="remove_timeout", description="Снять таймаут с пользователя")
    @app_commands.describe(member="С кого снять таймаут", reason="Причина (необязательно)")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def remove_timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Причина не указана",
    ):
        if member.timed_out_until is None:
            await interaction.response.send_message(
                "У этого пользователя нет активного таймаута.", ephemeral=True
            )
            return

        try:
            await member.timeout(None, reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "Не хватает прав для снятия таймаута.", ephemeral=True
            )
            return

        embed = discord.Embed(title="✅ Таймаут снят", color=discord.Color.green())
        embed.add_field(name="Пользователь", value=member.mention, inline=True)
        embed.add_field(name="Модератор", value=interaction.user.mention, inline=True)
        embed.add_field(name="Причина", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
