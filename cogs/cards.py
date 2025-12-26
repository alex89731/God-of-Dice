from discord.ext import commands
import discord
import random

class Cards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.suits = ['♠', '♥', '♦', '♣']
        self.ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

    def create_deck(self):
        deck = [f"{rank}{suit}" for suit in self.suits for rank in self.ranks]
        deck.extend(["Red Joker", "Black Joker"])
        return deck

    def format_card(self, card):
        if card == "Red Joker":
            return "🃏 **Red Joker**"
        if card == "Black Joker":
            return "🃏 Black Joker"
        return card

    @commands.command(name="drawcard")
    async def draw_card(self, ctx, count: int = 1):
        if count < 1 or count > 10:
            await ctx.send("Количество карт: от 1 до 10")
            return

        deck = self.create_deck()
        random.shuffle(deck)
        drawn = deck[:count]

        cards_formatted = [self.format_card(c) for c in drawn]
        response = f"**{ctx.author.display_name}** вытянул {count} карт: " + ", ".join(cards_formatted)

        await ctx.send(response)

    @commands.command(name="drawcarb")
    async def carb(self, ctx):
        """Всегда вытягивает красного джокера (для прикола)"""
        await ctx.send(f"**{ctx.author.display_name}** вытянул: 🃏 **Red Joker**")

async def setup(bot):
    await bot.add_cog(Cards(bot))