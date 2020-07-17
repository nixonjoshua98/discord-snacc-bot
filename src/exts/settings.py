import discord
from discord.ext import commands

from src.common.models import ServersM


class Settings(commands.Cog):

	async def cog_before_invoke(self, ctx: commands.Context):
		""" Ensure that we have an entry for the guild in the database. """

		_ = await ctx.bot.get_server(ctx.guild)

	async def cog_after_invoke(self, ctx):
		await ctx.bot.update_server_cache(ctx.message.guild)

	@commands.has_permissions(administrator=True)
	@commands.command(name="prefix")
	async def set_prefix(self, ctx: commands.Context, prefix: str):
		""" [Admin] Set the prefix for this server. """

		await ServersM.set(ctx.bot.pool, ctx.guild.id, prefix=prefix)

		await ctx.send(f"Prefix has been updated to `{prefix}`")

	@commands.has_permissions(administrator=True)
	@commands.command(name="setdefaultrole")
	async def set_default_role(self, ctx: commands.Context, role: discord.Role = None):
		""" [Admin] Set (or remove) the default role which gets added to each member when they join the server. """

		if role is not None and role > ctx.guild.me.top_role:
			return await ctx.send(f"I cannot use the role `{role.name}` since the role is higher than me.")

		await ServersM.set(ctx.bot.pool, ctx.guild.id, default_role=getattr(role, "id", 0))

		if role is None:
			await ctx.send(f"Default role has been removed")

		else:
			await ctx.send(f"The default role has been set to `{role.name}`")

	@commands.has_permissions(administrator=True)
	@commands.command(name="setmemberrole")
	async def set_member_role(self, ctx: commands.Context, role: discord.Role = None):
		""" [Admin] Set (or remove) the member role which can open up server-specific commands for server regulars. """

		await ServersM.set(ctx.bot.pool, ctx.guild.id, member_role=getattr(role, "id", 0))

		if role is None:
			await ctx.send(f"The member role has been removed.")

		else:
			await ctx.send(f"The member role has been set to `{role.name}`")


def setup(bot):
	bot.add_cog(Settings())
