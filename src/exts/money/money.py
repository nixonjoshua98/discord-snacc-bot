import random

from discord.ext import commands

from src.common.models import BankM
from src.common.converters import NormalUser

from .moneyleaderboard import MoneyLeaderboard


class Money(commands.Cog):

	@commands.cooldown(1, 60 * 60, commands.BucketType.user)
	@commands.command(name="free")
	async def free_money(self, ctx):
		""" Gain some free money """

		money = random.randint(500, 750)

		await ctx.bot.pool.execute(BankM.ADD_MONEY, ctx.author.id, money)

		await ctx.send(f"You gained **${money:,}**!")

	@commands.command(name="balance", aliases=["bal"])
	async def balance(self, ctx):
		""" Show your bank balance. """

		row = await BankM.get_row(ctx.bot.pool, ctx.author.id)

		await ctx.send(f":moneybag: **{ctx.author.display_name}** has **${row['money']:,}**")

	@commands.cooldown(1, 60 * 60, commands.BucketType.user)
	@commands.command(name="steal", cooldown_after_parsing=True)
	async def steal_coins(self, ctx, target: NormalUser()):
		""" Attempt to steal from another user. """

		async with ctx.bot.pool.acquire() as con:
			target_bank = await BankM.get_row(con, target.id)

			target_money = target_bank["money"]

			stolen_amount = random.randint(max(1, int(target_money * 0.025)), max(1, int(target_money * 0.075)))

			thief_tax = stolen_amount // random.randint(5, 10) if stolen_amount >= 1_000 else 0

			await con.execute(BankM.ADD_MONEY, ctx.author.id, stolen_amount - thief_tax)
			await con.execute(BankM.SUB_MONEY, target.id, stolen_amount)

		s = f"You stole **${stolen_amount:,}** from **{target.display_name}**."

		if thief_tax > 0:
			s = s[0:-1] + f" but the thief you hired took a cut of **${thief_tax:,}**."

		await ctx.send(s)

		# 12.5% chance for cooldown to be reset
		if random.randint(0, 7) == 0:
			self.steal_coins.reset_cooldown(ctx)

			await ctx.send("Good news! Your cooldown has been reset and you are ready to steal again.")

	@commands.cooldown(1, 60, commands.BucketType.guild)
	@commands.command(name="richest")
	async def show_richest_leaderboard(self, ctx):
		""" Display the richest players. """

		await MoneyLeaderboard().send(ctx)
