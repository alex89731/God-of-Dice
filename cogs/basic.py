from discord.ext import commands
import discord
import random
import re

PREFIX = '!'

class Basic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def roll_single(self, sides: int, explode: bool = True) -> tuple[int, list[int]]:
        results = []
        total = 0
        while True:
            roll = random.randint(1, sides)
            results.append(roll)
            total += roll
            if not explode or roll < sides:
                break
        return total, results

    async def do_skill_roll(self, message: discord.Message, sides: int, modifier: int, wild: bool, explode: bool):
        main_total, main_rolls = self.roll_single(sides, explode)
        wild_total, wild_rolls = 0, []
        if wild:
            wild_total, wild_rolls = self.roll_single(6, True)

        highest = max(main_total, wild_total) if wild else main_total
        highest += modifier

        successes = 1 if highest >= 4 else 0
        raises = (highest - 4) // 4 if highest >= 4 else 0

        main_part = f"[{main_total}; d{sides}]"
        wild_part = f" [{wild_total}; d6]" if wild else ""

        response = f"{main_part}{wild_part}"
        if modifier != 0:
            response += f"{modifier:+d}"
        response += f" = **{highest}**"

        if (wild and main_total == 1 and wild_total == 1) or (not wild and main_total == 1):
            response += " Глаза Змеи!"
        else:
            response += f" (Успехов: {successes}; Подъёмов: {raises})"

        await message.reply(response, mention_author=False)

    def roll_damage(self, expr: str) -> tuple[int, str]:
        expr = expr.replace(' ', '').lower()
        raw_parts = re.split(r'(?=[+-])', expr)
        parts = [p for p in raw_parts if p]
        if not parts:
            return 0, "Ошибка: пустое выражение"
        total = 0
        output_parts = []
        for part in parts:
            if re.match(r'^[+-]?\d+$', part):
                mod = int(part)
                total += mod
                if mod != 0:
                    output_parts.append(f"{mod:+d}")
                continue
            match = re.match(r'^([+-]?)(\d*)d(\d+)$', part)
            if not match:
                continue
            sign_char, count_str, sides_str = match.groups()
            sign = -1 if sign_char == '-' else 1
            count = int(count_str) if count_str else 1
            sides = int(sides_str)
            die_totals = []
            die_details = []
            for _ in range(count):
                die_total, die_rolls = self.roll_single(sides, explode=True)
                die_totals.append(die_total)
                if len(die_rolls) == 1:
                    die_details.append(str(die_rolls[0]))
                else:
                    die_details.append(' + '.join(map(str, die_rolls[:-1])) + f" → {die_rolls[-1]}")
            part_total = sign * sum(die_totals)
            total += part_total
            if count == 1:
                dice_str = f"d{sides}: {die_details[0]}"
            else:
                individual = ' + '.join(map(str, die_totals))
                dice_str = f"{count}d{sides}: {individual} = {sum(die_totals)}"
            if sign < 0:
                dice_str = "-" + dice_str
            output_parts.append(dice_str)
        response = "; ".join(output_parts) + f" **= {total}** урона"
        return total, response

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.content.startswith(PREFIX):
            ctx = await self.bot.get_context(message)
            if ctx.valid:
                return

        content = message.content.strip()

        # Навыки: !s8+2 !e10-1 !d6
        skill_match = re.match(r'^!([sed])(\d{1,2})([+-]\d+)?$', content, re.IGNORECASE)
        if skill_match:
            mode, sides_str, mod_str = skill_match.groups()
            sides = int(sides_str)
            if not 4 <= sides <= 20:
                return
            modifier = int(mod_str) if mod_str else 0
            if mode.lower() == 's':
                await self.do_skill_roll(message, sides, modifier, True, True)
            elif mode.lower() == 'e':
                await self.do_skill_roll(message, sides, modifier, False, True)
            elif mode.lower() == 'd':
                await self.do_skill_roll(message, sides, modifier, False, False)
            return

        # Урон: !2d6+d4+2!
        damage_match = re.match(r'^!(.+?)!$', content)
        if damage_match:
            expr = damage_match.group(1)
            total, response = self.roll_damage(expr)
            await message.reply(response, mention_author=False)
            return

        await self.bot.process_commands(message)

async def setup(bot):
    await bot.add_cog(Basic(bot))