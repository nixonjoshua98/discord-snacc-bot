

from discord.ext import commands

from src import inputs
from src.common import checks
from src.common.converters import EmpireUpgrade, Range

from src.structs.textpage import TextPage

from src.data import EmpireUpgrades


class Shop(commands.Cog):

	@staticmethod
	def create_pages(user_upgrades):
		pages = []

		for title, upgrades in EmpireUpgrades.groups.items():
			page = TextPage(title=title, headers=["ID", "Name", "Owned", "Cost"])

			for upgrade in upgrades:
				owned = user_upgrades.get(upgrade.key, 0)

				if owned < upgrade.max_amount:
					price = f"${upgrade.calc_price(owned, 1):,}"
					owned = f"{owned}/{upgrade.max_amount}"

					page.add([upgrade.id, upgrade.display_name, owned, price])

			page.set_footer("No upgrades available to buy" if len(page.rows) == 0 else None)

			pages.append(page.get())

		return pages

	@checks.has_empire()
	@commands.group(name="shop", invoke_without_command=True)
	async def shop_group(self, ctx):
		""" Display your shop. """

		upgrades = await ctx.bot.mongo.find_one("upgrades", {"_id": ctx.author.id})

		await inputs.send_pages(ctx, self.create_pages(upgrades))

	@checks.has_empire()
	@commands.max_concurrency(1, commands.BucketType.user)
	@shop_group.command(name="buy")
	async def buy_upgrade(self, ctx, upgrade: EmpireUpgrade(), amount: Range(1, 100) = 1):
		""" Buy a new upgrade. """

		# - Get data from database
		bank = await ctx.bot.mongo.find_one("bank", {"_id": ctx.author.id})
		upgrades = await ctx.bot.mongo.find_one("upgrades", {"_id": ctx.author.id})

		price = upgrade.calc_price(upgrades.get(upgrade.key, 0), amount)

		# - Reached the owned limit
		if upgrades.get(upgrade.key, 0) + amount > upgrade.max_amount:
			await ctx.send(f"**{upgrade.display_name}** have an owned limit of **{upgrade.max_amount}**.")

		# - User cannot afford upgrade
		elif price > bank.get("usd", 0):
			await ctx.send(f"You can't afford to hire **{amount}x {upgrade.display_name}**")

		else:
			# - Update database
			await ctx.bot.mongo.decrement_one("bank", {"_id": ctx.author.id}, {"usd": price})
			await ctx.bot.mongo.increment_one("upgrades", {"_id": ctx.author.id}, {upgrade.key: amount})

			await ctx.send(f"Bought **{amount}x {upgrade.display_name}** for **${price:,}**!")


def setup(bot):
	bot.add_cog(Shop())
