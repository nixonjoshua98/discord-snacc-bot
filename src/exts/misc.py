import os
import httpx

from discord.ext import commands

import datetime as dt
from bs4 import BeautifulSoup


class Miscellaneous(commands.Cog, name="Misc"):

	@commands.is_nsfw()
	@commands.command(name="urban")
	async def urban_dict(self, ctx, *, term):
		""" Look up a term in urbandictionary.com """

		url = f"https://mashape-community-urban-dictionary.p.rapidapi.com/define?term={term}"

		headers = {
			'x-rapidapi-host': "mashape-community-urban-dictionary.p.rapidapi.com",
			'x-rapidapi-key': os.getenv("RAID_API_KEY")
		}

		async with httpx.AsyncClient() as client:
			r = await client.get(url, headers=headers)

		if r.status_code != httpx.codes.OK:
			return await ctx.send(f"I failed to lookup your query. Status Code: {r.status_code}")

		data = r.json()

		embed = ctx.bot.embed(title=term)

		for i, d in enumerate(data["list"][:5], start=1):
			def_ = d['definition'].strip().replace("[", "").replace("]", "").replace("\n", "")
			exa = d['example'].strip().replace("[", "").replace("]", "").replace("\n", "")

			value = f"{def_}\n\n{exa}"
			value = value[:1021] + "..." if len(value) > 1024 else value

			embed.add_field(name="Definition & Example", value=value, inline=False)

		await ctx.send(embed=embed)

	@commands.command(name="whatis")
	async def what_is_this(self, ctx, *, word: str):
		""" Look for a word definition. """

		word = word.lower()

		async with httpx.AsyncClient() as client:
			r = await client.get(f"http://dictionary.reference.com/browse/{word.replace(' ', '_')}?s=t")

		if r.status_code != httpx.codes.OK:
			return await ctx.send(f"I failed to lookup your query. Status Code: {r.status_code}")

		# Soup extracting
		soup = BeautifulSoup(r.content, "html.parser")
		defs = soup.find(class_="css-1urpfgu e16867sm0").find_all(class_="one-click-content css-1p89gle e1q3nk1v4")

		# Create list of definitions
		definitions = [txt for txt in map(lambda ele: ele.text.strip(), defs) if not txt[0].isupper()]
		definitions = [f"{i}. {d}" for i, d in enumerate(definitions, start=1)]

		if len(definitions) > 0:
			value = "\n".join(definitions)
			value = value[:1021] + "..." if len(value) > 1024 else value

			embed = ctx.bot.embed(title=word)

			embed.add_field(name="Definition(s)", value=value)

			return await ctx.send(embed=embed)

		await ctx.send("I found no definitions or examples for your query.")

	@commands.command(name="cooldowns", aliases=["cd"])
	async def cooldowns(self, ctx):
		""" Display your command cooldowns. """

		embed = ctx.bot.embed(title="Cooldowns", author=ctx.author)

		for name, inst in ctx.bot.cogs.items():
			cooldowns = []

			for cmd in inst.walk_commands():

				if cmd._buckets._cooldown:
					try:
						if not await cmd.can_run(ctx):
							continue
					except commands.CommandError:
						continue

					current = ctx.message.created_at.replace(tzinfo=dt.timezone.utc).timestamp()

					bucket = cmd._buckets.get_bucket(ctx.message, current)

					if bucket._tokens == 0:
						retry_after = bucket.per - (current - bucket._window)

						if retry_after > 0:
							cooldowns.append(f"`{cmd.name: <12} {dt.timedelta(seconds=int(retry_after))}`")

			if cooldowns:
				embed.add_field(name=name, value="\n".join(cooldowns))

		await ctx.send(embed=embed)


def setup(bot):
	bot.add_cog(Miscellaneous())
