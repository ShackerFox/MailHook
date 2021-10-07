import logging
import asyncio
import os
import discord
import hikari
import aiohttp_cors
from typing import List
from discord.ext import commands
from utils.bot import ModMail
from aiohttp import web, ClientSession


try:
    import uvloop
    uvloop.install()
except Exception:
    pass


class Guild:
    def __init__(self, id: str, name: str, icon: str, owner: bool, permissions: int, features: List[str], permissions_new: str):
        self.id: str = id
        self.name: str = name
        self.icon: str = icon
        self.owner: bool = owner
        self.permissions: int = permissions
        self.features: List[str] = features
        self.permissions_new: str = permissions_new

    def __str__(self) -> str:
        return f"<Guild name='{self.name}' id={self.id}>"

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def icon_url(self) -> str:
        return f"https://cdn.discordapp.com/icons/{self.id}/{self.icon}.png"


class WebServer(commands.Cog):
    def __init__(self, client: ModMail):
        self.client = client
        self.rest_api = hikari.RESTApp()
        self.api = None
        self.BASE = "https://discord.com/api"
        self.REDIRECT_URI = "https://mailhook-beta.netlify.app/callback"
        # self.REDIRECT_URI = "http://localhost:3000/callback"
        self.cors_thing = {
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        }

    def filter_guilds(self, user_guilds: List[Guild], bot_guilds: List[discord.Guild]) -> List[Guild]:
        mutual_guilds: List[Guild] = []
        bot_guild_ids = [g.id for g in bot_guilds]
        for guild in user_guilds:
            if int(guild.id) in bot_guild_ids:
                mutual_guilds.append(guild)
        return [g for g in mutual_guilds if g.permissions & hikari.Permissions.MANAGE_GUILD]

    async def get_access_token(self, code: str) -> dict:
        async with ClientSession() as session:
            async with session.post(
                f"{self.BASE}/oauth2/token",
                data={
                    "client_id": str(self.client.user.id),
                    "client_secret": self.client.config.client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.REDIRECT_URI,
                },
            ) as resp:
                return await resp.json()

    async def get_user(self, token: str) -> hikari.OwnUser:
        async with self.rest_api.acquire(token) as client:
            return await client.fetch_my_user()

    async def get_user_guilds(self, token: str) -> List[Guild]:
        async with ClientSession() as session:
            async with session.get(
                f"{self.BASE}/users/@me/guilds",
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                data = await resp.json()
                return [Guild(**g) for g in data]

    async def callback(self, request: web.Request):
        code = (await request.json()).get("code").get("code")
        if code is None:
            raise web.HTTPBadRequest()
        data = await self.get_access_token(code)
        return web.json_response({"access_token": data.get("access_token")})

    async def get_own_user(self, request: web.Request):
        access_token = request.headers.get("access_token")
        if access_token is None:
            raise web.HTTPBadRequest()
        user = await self.get_user(access_token)
        return web.json_response({
            "id": user.id,
            "username": user.username,
            "discriminator": user.discriminator,
            "avatar": str(user.avatar_url)
        })

    async def get_guilds(self, request: web.Request):
        access_token = request.headers.get("access_token")
        if access_token is None:
            raise web.HTTPBadRequest()

        user_guilds = await self.get_user_guilds(access_token)
        bot_guilds = self.client.guilds
        valid_guilds = self.filter_guilds(user_guilds, bot_guilds)

        return web.json_response({
            "guilds": [{
                "id": g.id,
                "name": g.name,
                "icon_url": g.icon_url,
            } for g in valid_guilds]
        })

    async def get_guild_data(self, request: web.Request):
        guild_id = request.headers.get("guild_id")
        if guild_id is None:
            raise web.HTTPBadRequest()
        try:
            int(guild_id)
        except ValueError:
            return web.json_response({"error": "Invalid guild id"})
        guild = self.client.get_guild(int(guild_id))
        if guild is None:
            return web.json_response({"error": "Guild not found"})
        guild_data = await self.client.mongo.get_guild_data(guild.id, raise_error=False)
        if guild_data is not None:
            modrole = guild.get_role(guild_data['staff_role'])
            ticket_category = guild.get_channel(guild_data['category'])
            transcripts_channel = guild.get_channel(guild_data['transcripts'])
            current_tickets = await self.client.mongo.get_guild_modmail_threads(guild.id)

        return web.json_response({
            "id": str(guild.id),
            "name": guild.name,
            "description": guild.description,
            "icon": guild.icon.url if guild.icon is not None else "https://cdn.discordapp.com/embed/avatars/0.png",
            "banner": guild.banner.url if guild.banner is not None else None,
            "members": guild.member_count,
            "owner": {
                "id": guild.owner.id,
                "username": guild.owner.name,
                "discriminator": guild.owner.discriminator,
                "avatar": guild.owner.display_avatar.url
            } if guild.owner is not None else None,
            "settings": {
                "prefixes": self.client.config.prefixes,
                "modRole": {
                    "id": modrole.id,
                    "name": modrole.name,
                    "color": str(modrole.color),
                } if modrole is not None else None,
                "ticketCategory": {
                    "id": ticket_category.id,
                    "name": ticket_category.name,
                } if ticket_category is not None else None,
                "transcriptsChannel": {
                    "id": transcripts_channel.id,
                    "name": transcripts_channel.name,
                } if transcripts_channel is not None else None,
                "currentTickets": [{
                    "userId": ticket['_id'],
                    "channelId": ticket['channel_id']
                } for ticket in current_tickets]
            } if guild_data is not None else None,
        })

    async def bot_stats(self, request: web.Request):
        return web.json_response({
            "guilds": len(self.client.guilds),
            "users": len(self.client.users),
            "ping": round(self.client.latency * 1000, 2),
        })

    async def start_server(self):
        app = web.Application()
        cors = aiohttp_cors.setup(app)

        callback_resource = cors.add(app.router.add_resource("/oauth/callback"))
        get_own_user_resource = cors.add(app.router.add_resource("/users/me"))
        get_guilds_resource = cors.add(app.router.add_resource("/guilds"))
        get_guild_data_resource = cors.add(app.router.add_resource("/guild"))
        bot_stats_resource = cors.add(app.router.add_resource("/stats"))

        cors.add(callback_resource.add_route("POST", self.callback), self.cors_thing)
        cors.add(get_own_user_resource.add_route("GET", self.get_own_user), self.cors_thing)
        cors.add(get_guilds_resource.add_route("GET", self.get_guilds), self.cors_thing)
        cors.add(get_guild_data_resource.add_route("GET", self.get_guild_data), self.cors_thing)
        cors.add(bot_stats_resource.add_route("GET", self.bot_stats), self.cors_thing)

        runner = web.AppRunner(app)
        await runner.setup()

        self.api = web.TCPSite(runner, host="0.0.0.0", port=os.environ.get("PORT", 8080))
        await self.client.wait_until_ready()
        await self.api.start()
        logging.info(f"Web server started at PORT: {self.api._port} HOST: {self.api._host}")

    def cog_unload(self) -> None:
        asyncio.ensure_future(self.api.stop())
        logging.info("Web server stopped")


def setup(client: ModMail):
    cog = WebServer(client)
    client.add_cog(cog)
    client.loop.create_task(cog.start_server())
