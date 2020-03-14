import discord
import os

from discord.ext import commands

from src import cogs
from src.common import (myjson, asycio_schedule)
from src.common import FileReader


class MyBot(commands.Bot):
	def __init__(self):
		super().__init__(command_prefix=MyBot.prefix, case_insensitive=True)

		self.help_command = commands.DefaultHelpCommand()

		myjson.download_all_files()

	async def on_ready(self):
		await self.wait_until_ready()

		print("Bot successfully started")

		for c in cogs.ALL_COGS:
			print(f"Added Cog: {c.__name__}")

			self.add_cog(c(self))

		asycio_schedule.add_task(60 * 5, myjson.backup_background_task, 60 * 5)

	async def on_command_error(self, ctx, esc):
		return await ctx.send(esc)

	async def on_message(self, message: discord.Message):
		if message.guild is None:
			return

		await self.process_commands(message)

	@staticmethod
	def prefix(bot: commands.Bot, message: discord.message):
		if os.getenv("DEBUG", False):
			return "-"

		with FileReader("server_settings.json") as server_settings:
			prefix = server_settings.get_inner_key(str(message.guild.id), "prefix", "!")

		return prefix

	def run(self):
		super().run("NjY2NjE2NTE1NDM2NDc4NDcz.Xh2xCA.X8d9IFcSW_2e4c_maBMoXlxmI7Y")