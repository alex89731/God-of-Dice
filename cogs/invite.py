from discord.ext import commands

class Invite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="invite")
    async def invite(self, ctx):
        invite_link = "https://discord.com/oauth2/authorize?client_id=1422683057567301714&permissions=84992&integration_type=0&scope=bot"
        await ctx.send(invite_link)

async def setup(bot):
    await bot.add_cog(Invite(bot))