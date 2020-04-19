import discord
import asyncio
import random

from discord.ext import commands

from bot.common.constants import DARKNESS_GUILD


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        await self.rgb_loop()

    async def cog_check(self, ctx):
        return ctx.guild.id == DARKNESS_GUILD

    async def rgb_loop(self):
        def get_colour():
            return discord.Colour.from_rgb(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

        while True:
            guild = self.bot.get_guild(DARKNESS_GUILD)

            role = discord.utils.get(guild.roles, name="RGB")

            if role is None:
                continue

            try:
                await role.edit(colour=get_colour())

            except (discord.Forbidden, discord.HTTPException) as e:
                print(e)

            await asyncio.sleep(5)


def setup(bot):
    bot.add_cog(Misc(bot))
