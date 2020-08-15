

import random
import discord
import itertools

import datetime as dt

from discord.ext import tasks, commands

from src import inputs
from src.common import MainServer, checks
from src.common.converters import EmpireTargetUser

from src.data import MilitaryGroup, MoneyGroup

from src.exts.empire import events


MAX_HOURS_OFFLINE = 8


class Empire(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

		self.currently_adding_income = False

		print("Starting loop: Income")

		self.income_loop.start()

	async def cog_before_invoke(self, ctx):
		if ctx.guild.id == MainServer.ID:
			await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, id=MainServer.EMPIRE_ROLE))

	async def cog_after_invoke(self, ctx):
		await ctx.bot.mongo.update_one("empires", {"_id": ctx.author.id}, {"last_login": dt.datetime.utcnow()})

	@staticmethod
	def get_win_chance(atk_power, def_power):
		return max(0.15, min(0.85, ((atk_power / max(1, def_power)) / 2.0)))

	async def calculate_units_lost(self, population, upgrades):
		units_lost = dict()
		units_lost_cost = 0

		hourly_income = max(0, MoneyGroup.get_total_hourly_income(population, upgrades))

		available_units = list(itertools.filterfalse(lambda u: population[u.key] == 0, MilitaryGroup.units))

		available_units.sort(key=lambda u: u.price(upgrades, population[u.key]), reverse=False)

		for unit in available_units:
			for i in range(1, population[unit.key] + 1):
				price = unit.price(upgrades, population[unit.key] - i, i)

				if (price + units_lost_cost) < hourly_income:
					units_lost[unit] = i

				units_lost_cost = sum([u.get_price(population[unit.key] - n, n) for u, n in units_lost.items()])

		return units_lost

	@staticmethod
	async def calculate_money_lost(bank):
		return random.randint(max(1, int(bank.get("usd", 0) * 0.025)), max(1, int(bank.get("usd", 0) * 0.05)))

	@checks.no_empire()
	@commands.command(name="create")
	@commands.max_concurrency(1, commands.BucketType.user)
	async def create_empire(self, ctx, empire_name: str):
		""" Establish an empire under your name. """

		now = dt.datetime.utcnow()

		row = dict(name=empire_name, last_login=now, last_income=now)

		await ctx.bot.mongo.update_one("empires", {"_id": ctx.author.id}, row)

		await ctx.send(f"Your empire has been established! You can rename your empire using `{ctx.prefix}rename`")

		await self.show_empire(ctx)

	@checks.has_empire()
	@commands.max_concurrency(1, commands.BucketType.user)
	@commands.command(name="empire", aliases=["e"])
	async def show_empire(self, ctx):
		""" View your empire. """

		empire = await ctx.bot.mongo.find_one("empires", {"_id": ctx.author.id})
		workers = await ctx.bot.mongo.find_one("workers", {"_id": ctx.author.id})
		upgrades = await ctx.bot.mongo.find_one("upgrades", {"_id": ctx.author.id})
		military = await ctx.bot.mongo.find_one("military", {"_id": ctx.author.id})

		# - Calculate the values used in the Embed message
		hourly_income = MoneyGroup.get_total_hourly_income(workers, upgrades)
		hourly_upkeep = MilitaryGroup.get_total_hourly_upkeep(military, upgrades)

		total_power = MilitaryGroup.get_total_power(military)

		name = empire.get('name', 'No Name Empire')

		# - Create the Embed message which will be sent back to Discord
		embed = ctx.bot.embed(title=f"{str(ctx.author)}: {name}", thumbnail=ctx.author.avatar_url)

		embed.add_field(name="General", value=f"**Power Rating:** `{total_power:,}`")

		embed.add_field(name="Finances", value=f"**Income:** `${hourly_income:,}`\n**Upkeep:** `${hourly_upkeep:,}`")

		await ctx.send(embed=embed)

	@checks.has_empire()
	@commands.command(name="rename")
	async def rename_empire(self, ctx, *, new_name):
		""" Rename your established empire. """

		await self.bot.mongo.update_one("empires", {"_id": ctx.author.id}, {"name": new_name})

		await ctx.send(f"Your empire has been renamed to `{new_name}`")

	@checks.has_empire()
	@commands.max_concurrency(1, commands.BucketType.user)
	@commands.command(name="collect")
	async def collect_income(self, ctx):
		""" Collect your hourly income. """

		now = dt.datetime.utcnow()

		# - Load data from database
		empire = await ctx.bot.mongo.find_one("empires", {"_id": ctx.author.id})
		upgrades = await ctx.bot.mongo.find_one("upgrades", {"_id": ctx.author.id})
		workers = await ctx.bot.mongo.find_one("workers", {"_id": ctx.author.id})
		military = await ctx.bot.mongo.find_one("military", {"_id": ctx.author.id})

		# - Calculate passive income
		if empire.get("last_income") is not None:
			hours = min(MAX_HOURS_OFFLINE, (now - empire["last_income"]).total_seconds() / 3600)

			hourly_income = MoneyGroup.get_total_hourly_income(workers, upgrades)
			hourly_upkeep = MilitaryGroup.get_total_hourly_upkeep(military, upgrades)

			money_change = int((hourly_income + hourly_upkeep) * hours)

			# - Update database
			await ctx.bot.mongo.increment_one("bank", {"_id": empire["_id"]}, {"usd": money_change})

			await ctx.send(f"You received **${money_change:,}**")

		else:
			await ctx.send("Failed to collect. Try again")

		await ctx.bot.mongo.update_one("empires", {"_id": empire["_id"]}, {"last_income": now})

	@checks.has_empire()
	@commands.cooldown(1, 15, commands.BucketType.user)
	@commands.command(name="scout", cooldown_after_parsing=True)
	async def scout(self, ctx, *, target: EmpireTargetUser()):
		""" Pay to scout an empire to recieve valuable information. """

		# - Load data from database
		author_bank = await ctx.bot.mongo.find_one("bank", {"_id": ctx.author.id})
		author_military = await ctx.bot.mongo.find_one("military", {"_id": ctx.author.id})
		target_military = await ctx.bot.mongo.find_one("military", {"_id": target.id})

		author_power = MilitaryGroup.get_total_power(author_military)
		target_power = MilitaryGroup.get_total_power(target_military)

		if author_bank.get("usd", 0) < 500:
			await ctx.send(f"Scouting an empire costs **$500**.")

		else:
			# - Update database
			await ctx.bot.mongo.decrement_one("bank", {"_id": ctx.author.id}, {"usd": 500})

			win_chance = self.get_win_chance(author_power, target_power)

			await ctx.send(
				f"You hired a scout for **$500**. "
				f"You have a **{int(win_chance * 100)}%** chance of winning against **{target.display_name}**."
			)

	@checks.has_empire()
	@commands.cooldown(1, 60 * 120, commands.BucketType.user)
	@commands.command(name="attack", cooldown_after_parsing=True)
	async def attack(self, ctx, *, target: EmpireTargetUser()):
		""" Attack a rival empire. """

		# - Load the populations of each empire
		target_military = await ctx.bot.mongo.find_one("military", {"_id": target.id})
		author_military = await ctx.bot.mongo.find_one("military", {"_id": ctx.author.id})

		# - Power ratings of each empire which is used to calculate the win chance for the author (attacker)
		target_power = MilitaryGroup.get_total_power(target_military)
		author_power = MilitaryGroup.get_total_power(author_military)

		win_chance = self.get_win_chance(author_power, target_power)

		# - Author won the attack
		if win_chance >= random.uniform(0.0, 1.0):
			target_bank = await ctx.bot.mongo.find_one("bank", {"_id": target.id})
			target_empire = await ctx.bot.mongo.find_one("empires", {"_id": target.id})
			target_upgrades = await ctx.bot.mongo.find_one("upgrades", {"_id": target.id})

			money_stolen = await self.calculate_money_lost(target_bank)

			units_lost = await self.calculate_units_lost(target_military, target_upgrades)

			bonus_money = int(money_stolen * (1.0 - win_chance) if win_chance <= 0.5 else 0)

			await ctx.bot.mongo.increment_one("bank", {"_id": ctx.author.id}, {"usd": money_stolen+bonus_money})
			await ctx.bot.mongo.decrement_one("bank", {"_id": target.id}, {"usd": money_stolen + bonus_money})

			if units_lost:
				await ctx.bot.mongo.decrement_one(
					"military",
					{"_id": target.id},
					{k.key: v for k, v in units_lost.items()}
				)

				# - Put the target empire into a 'cooldown' so they cannot get attacked for a period of time
				await ctx.bot.mongo.update_one("empires", {"_id": target.id}, {"last_attack": dt.datetime.utcnow()})

				# - Create the message to return to Discord
				units_text = "\n".join(map(lambda kv: f"{kv[1]}x {kv[0].display_name}", units_lost.items()))
				val = f"${money_stolen:,} {f'**+ ${bonus_money:,} bonus**' if bonus_money > 0 else ''}"

				embed = ctx.bot.embed(title=f"Attack on {str(target)}: {target_empire['name']}")

				embed.description = f"**Money Pillaged:** {val}"

				if units_text:
					embed.add_field(name="Units Killed", value=units_text)

				await ctx.send(embed=embed)

		else:
			author_bank = await ctx.bot.mongo.find_one("bank", {"_id": ctx.author.id})

			money_lost = await self.calculate_money_lost(author_bank)

			await ctx.bot.mongo.decrement_one("bank", {"_id": ctx.author.id}, {"usd": money_lost})

			await ctx.send(f"Your attack on **{target.display_name}** failed and you lost **${money_lost:,}**")

		# - Take the author out of their cooldown
		day_ago = dt.datetime.utcnow() - dt.timedelta(hours=24.0)

		await ctx.bot.mongo.update_one("empires", {"_id": ctx.author.id}, {"last_attack": day_ago})

	@checks.has_empire()
	@commands.cooldown(1, 60 * 90, commands.BucketType.user)
	@commands.command(name="empireevent", aliases=["ee"])
	async def empire_event(self, ctx):
		""" Trigger an empire event. """

		options = (events.loot_event, events.stolen_event, events.assassinated_event, events.recruit_unit)
		weights = (85, 10, 10, 25)

		chosen_events = random.choices(options, weights=weights, k=1)

		for event in chosen_events:
			await event(ctx)

	@commands.cooldown(1, 15, commands.BucketType.guild)
	@commands.command(name="power", aliases=["empires"])
	async def power_leaderboard(self, ctx):
		""" Display the most powerful empires. """

		async def query():
			empires = await ctx.bot.mongo.find("military").to_list(length=100)

			for i, row in enumerate(empires):
				empires[i] = dict(**row, __power__=MilitaryGroup.get_total_power(row))

			empires.sort(key=lambda ele: ele["__power__"], reverse=True)

			return empires

		await inputs.show_leaderboard(
			ctx,
			"Most Powerful Empires",
			columns=["__power__"],
			order_by="__power__",
			query_func=query,
			headers=["Power"]
		)

	@tasks.loop(hours=1.0)
	async def income_loop(self):
		""" Background income & upkeep loop. """

		self.currently_adding_income = True

		empires = await self.bot.mongo.find("empires").to_list(length=None)

		for empire in empires:
			now = dt.datetime.utcnow()

			# - Set the last_income field which is used to calculate the income rate from the delta time
			await self.bot.mongo.update_one("empires", {"_id": empire["_id"]}, {"last_income": now})

			last_login = empire.get("last_login", now)
			last_income = empire.get("last_income", now)

			hours_since_login = (now - last_login).total_seconds() / 3600

			# - User must have logged in the past 8 hours in order to get passive income
			if hours_since_login >= MAX_HOURS_OFFLINE:
				continue

			# - Query the database
			workers = await self.bot.mongo.find_one("workers", {"_id": empire["_id"]})
			upgrades = await self.bot.mongo.find_one("upgrades", {"_id": empire["_id"]})
			military = await self.bot.mongo.find_one("military", {"_id": empire["_id"]})

			# - Total number of hours we need to credit the empire's bank
			hours = (now - last_income).total_seconds() / 3600

			# - Hourly income/keep
			total_hourly_income = MoneyGroup.get_total_hourly_income(workers, upgrades)
			total_hourly_upkeep = MilitaryGroup.get_total_hourly_upkeep(military, upgrades)

			# - Overall money gained/lost per hour
			money_change = int((total_hourly_income - total_hourly_upkeep) * hours)

			if money_change > 0:
				await self.bot.mongo.increment_one("bank", {"_id": empire["_id"]}, {"usd": money_change})

			elif money_change < 0:
				await self.bot.mongo.decrement_one("bank", {"_id": empire["_id"]}, {"usd": abs(money_change)})

		self.currently_adding_income = False


def setup(bot):
	bot.add_cog(Empire(bot))
