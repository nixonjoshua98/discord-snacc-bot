import discord
from discord.ext import commands


class OnMessage(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.Cog.listener("on_message")
	async def on_message(self, message):
		if not await self.bot.on_message_check(message):
			return

		# Natsu
		if message.author.id == 305727745382678528:
			for react in ("<a:e1:715277287276281866>",):
				try:
					await message.add_reaction(react)

				except (discord.Forbidden, discord.HTTPException):
					""" Failed """


def setup(bot):
	bot.add_cog(OnMessage(bot))