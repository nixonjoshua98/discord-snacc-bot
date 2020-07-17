import math
import asyncio
import random

from discord.ext import tasks, commands

from datetime import datetime

from src import inputs
from src.common import checks
from src.common.models import BankM, EmpireM
from src.structs.textpage import TextPage
from src.common.converters import EmpireUnit, Range

from . import units
from . import empireevents as events

from .units import UnitGroupType


class Empire(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

		self.start_income_loop()

	def start_income_loop(self):
		async def predicate():
			if await self.bot.is_snacc_owner():
				print("Starting 'Empire.income_loop' loop.")

				self.income_loop.start()

		asyncio.create_task(predicate())

	@checks.no_empire()
	@commands.command(name="create")
	@commands.max_concurrency(1, commands.BucketType.user)
	async def create_empire(self, ctx, *, empire_name: str):
		""" Establish an empire under your name. """

		await ctx.bot.pool.execute(EmpireM.INSERT_ROW, ctx.author.id, empire_name)

		await ctx.send(f"Your empire named `{empire_name}` has been established!")

		await self.show_empire(ctx)

	@checks.has_empire()
	@commands.cooldown(1, 60 * 60, commands.BucketType.user)
	@commands.command(name="battle")
	async def battle(self, ctx):
		""" Attack a rival empire. """

		await ctx.send(str(self.battle.__doc__)[:2000])

	@checks.has_empire()
	@commands.cooldown(1, 60 * 60, commands.BucketType.user)
	@commands.command(name="empireevent", aliases=["ee"])
	async def empire_event(self, ctx):
		""" Trigger an empire event. """

		options = (events.ambush_event, events.treaure_event, events.stolen_event)
		weights = (25, 100, 25)

		chosen_events = random.choices(options, weights=weights, k=1)

		for event in chosen_events:
			await event(ctx)

		if random.randint(0, 9) == 0:
			self.empire_event.reset_cooldown(ctx)

			await ctx.send("Good news! Your cooldown has been reset.")

	@checks.has_empire()
	@commands.command(name="empire")
	async def show_empire(self, ctx):
		""" View your empire. """

		empire = await ctx.bot.pool.fetchrow(EmpireM.SELECT_ROW, ctx.author.id)

		pages = [group.create_empire_page(empire).get() for group in units.UNIT_GROUPS.values()]

		await inputs.send_pages(ctx, pages)

	@checks.has_empire()
	@commands.command(name="rename")
	async def rename_empire(self, ctx, *, empire_name):
		""" Rename your established empire. """

		await ctx.bot.pool.execute(EmpireM.UPDATE_NAME, ctx.author.id, empire_name)

		await ctx.send(f"Your empire has been renamed to `{empire_name}`")

	@checks.has_empire()
	@commands.command(name="units")
	async def show_units(self, ctx):
		""" Show all the possible units which you can buy. """

		empire = await ctx.bot.pool.fetchrow(EmpireM.SELECT_ROW, ctx.author.id)

		pages = [group.create_units_page(empire).get() for group in units.UNIT_GROUPS.values()]

		await inputs.send_pages(ctx, pages)

	@checks.has_empire()
	@commands.command(name="hire")
	@commands.max_concurrency(1, commands.BucketType.user)
	async def hire_unit(self, ctx, unit: EmpireUnit(), amount: Range(1, 100) = 1):
		""" Hire a new unit. """

		async with ctx.bot.pool.acquire() as con:
			empire = await con.fetchrow(EmpireM.SELECT_ROW, ctx.author.id)

			row = await BankM.get_row(con, ctx.author.id)

			price = unit.get_price(empire[unit.db_col], amount)

			user_money = row[BankM.MONEY]

			if price > user_money:
				await ctx.send(f"You can't afford to hire **{amount}x {unit.display_name}**")

			elif empire[unit.db_col] + amount > unit.max_amount:
				await ctx.send(f"You may only have a maximum of **{unit.max_amount}** of this unit")

			else:
				await con.execute(BankM.SUB_MONEY, ctx.author.id, price)

				await EmpireM.add_unit(con, ctx.author.id, unit, amount)

				await ctx.send(f"Bought **{amount}x {unit.display_name}** for **${price:,}**!")

	@tasks.loop(hours=1.0)
	async def income_loop(self):
		async with self.bot.pool.acquire() as con:
			rows = await con.fetch(EmpireM.SELECT_ALL)

			for empire in rows:
				now = datetime.utcnow()

				delta_time = (now - empire[EmpireM.LAST_INCOME]).total_seconds() / 3600

				money_change = 0

				for _, group in units.UNIT_GROUPS.items():
					for unit in group.units:
						money_change += unit.get_delta_money(empire[unit.db_col], delta_time)

				money_change = math.ceil(money_change)

				if money_change != 0:
					await con.execute(BankM.ADD_MONEY, empire[EmpireM.USER_ID], money_change)

				await con.execute(EmpireM.UPDATE_LAST_INCOME, empire[EmpireM.USER_ID], now)
