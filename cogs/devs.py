import discord
from handler import InteractionContext
from typing import Union
from utils.bot import ModMail
from discord.ext import commands


class Devs(commands.Cog):
    def __init__(self, bot: ModMail):
        self.bot = bot

    @commands.group()
    @commands.is_owner()
    async def blacklist(self, ctx: commands.Context):
        p = ctx.clean_prefix
        if ctx.invoked_subcommand is None:
            return await ctx.reply(f"Usage: `{p}blacklist add/remove @user [reason]`")

    @blacklist.command()
    @commands.is_owner()
    async def add(self, ctx: commands.Context, user: discord.Member = None, *, reason: str = None):
        if user is None:
            return await ctx.invoke(self.bot.get_command('blacklist'))
        await self.bot.mongo.blacklist(user.id, reason)
        await ctx.message.add_reaction('👌')
        await self.bot.mongo.get_blacklist_cache()

    @blacklist.command()
    @commands.is_owner()
    async def remove(self, ctx: commands.Context, user: discord.Member = None):
        if user is None:
            return await ctx.invoke(self.bot.get_command('blacklist'))
        await self.bot.mongo.unblacklist(user.id)
        await ctx.message.add_reaction('👌')
        await self.bot.mongo.get_blacklist_cache()

    @commands.Cog.listener('on_command')
    async def cmd_logs(self, ctx: Union[commands.Context, InteractionContext]):
        if not ctx.guild:
            return
        channel = self.bot.get_channel(self.bot.config.logs.cmds)
        await channel.send(embed=discord.Embed(
            title="Command used:",
            description=f"Command: `{ctx.message.content if isinstance(ctx, commands.Context) else ctx.command.name}`\nSlash?: {'True' if isinstance(ctx, InteractionContext) else 'False'}",
            color=discord.Color.blurple()
        ).set_author(name=f"{ctx.author} | {ctx.author.id}", icon_url=ctx.author.display_avatar.url
        ).add_field(name="Channel:", value=f"{ctx.channel.mention}\n#{ctx.channel.name} ({ctx.channel.id})"
        ).add_field(name="Guild:", value=f"{ctx.guild.name}\n{ctx.guild.id}"))

    @commands.Cog.listener('on_app_command')
    async def slash_cmd_logs(self, ctx):
        await self.cmd_logs(ctx)

    @commands.Cog.listener('on_guild_join')
    async def on_guild_join(self, guild: discord.Guild):
        text_to_send = f"""
Hey there! Thanks a lot for inviting me!
If you are a server admin then please visit https://mail-hook.xyz/setup/{guild.id} to setup this server.

If you face any issues, feel free to join our support server:
- https://discord.gg/TeSHENet9M
"""

        log_embed = discord.Embed(
            title="New guild joined",
            description=f"{guild.name} ({guild.id})",
            color=discord.Color.blurple()
        ).set_author(name=f"{guild.owner}", icon_url=guild.owner.display_avatar.url
        ).add_field(name="Humans:", value=f"{len(list(filter(lambda m: not m.bot, guild.members)))}"
        ).add_field(name="Bots:", value=f"{len(list(filter(lambda m: m.bot, guild.members)))}"
        ).set_footer(text=f"Owner ID: {guild.owner_id}")
        if guild.icon is not None:
            log_embed.set_thumbnail(url=guild.icon.url)

        await self.bot.get_channel(self.bot.config.logs.add_remove).send(embed=log_embed)

        for channel in guild.channels:
            if "general" in channel.name:
                try:
                    return await channel.send(text_to_send)
                except Exception:
                    pass

        for channel in guild.channels:
            if "bot" in channel.name or "cmd" in channel.name or "command" in channel.name:
                try:
                    return await channel.send(text_to_send)
                except Exception:
                    pass

        for channel in guild.channels:
            try:
                return await channel.send(text_to_send)
            except Exception:
                pass

    @commands.Cog.listener('on_guild_remove')
    async def on_guild_remove(self, guild: discord.Guild):
        log_embed = discord.Embed(
            title="Guild left",
            description=f"{guild.name} ({guild.id})",
            color=discord.Color.red()
        ).set_author(name=f"{guild.owner}", icon_url=guild.owner.display_avatar.url
        ).add_field(name="Humans:", value=f"{len(list(filter(lambda m: not m.bot, guild.members)))}"
        ).add_field(name="Bots:", value=f"{len(list(filter(lambda m: m.bot, guild.members)))}"
        ).set_footer(text=f"Owner ID: {guild.owner_id}")
        if guild.icon is not None:
            log_embed.set_thumbnail(url=guild.icon.url)

        await self.bot.get_channel(self.bot.config.logs.add_remove).send(embed=log_embed)


def setup(bot: ModMail):
    bot.add_cog(Devs(bot))
