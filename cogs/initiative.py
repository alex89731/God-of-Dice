from discord.ext import commands
import discord
import random
import re


class InitiativeState:
    SUITS = ('♣', '♦', '♥', '♠')
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    JOKER = 'Joker'

    TRAIT_NAMES = {
        'q': 'стремительность',
        'l': 'хладнокровие',
        'i': 'хладнокровие+',
        'h': 'медлительность'
    }

    def __init__(self):
        self.deck = []
        self.discard = []
        self.current_round = {}
        self.on_hold = set()
        self.joker_this_round = False
        self.round_number = 0

    def full_deck(self):
        return [f"{r}{s}" for s in self.SUITS for r in self.RANKS] + [self.JOKER] * 2

    def shuffle_deck(self):
        full = self.deck + self.discard
        random.shuffle(full)
        self.deck = full
        self.discard = []

    def ensure_cards(self, needed=1):
        if len(self.deck) < needed:
            self.shuffle_deck()

    def draw_card(self):
        self.ensure_cards(1)
        card = self.deck.pop()
        self.discard.append(card)
        if card == self.JOKER:
            self.joker_this_round = True
        return card

    def card_value(self, card):
        if card == self.JOKER:
            return (100, 100)
        rank = card[:-1]
        return (self.RANKS.index(rank), self.SUITS.index(card[-1]))

    @staticmethod
    def format_card(card):
        return "**Joker**" if card == InitiativeState.JOKER else card

    @staticmethod
    def format_all_cards(cards):
        if not cards:
            return ""
        return "[" + ", ".join(InitiativeState.format_card(c) for c in cards) + "]"

    def get_trait_display(self, traits):
        active = []
        if traits.get('q'): active.append(self.TRAIT_NAMES['q'])
        if traits.get('i') or traits.get('l'): active.append(self.TRAIT_NAMES['i'])
        if traits.get('h'): active.append(self.TRAIT_NAMES['h'])
        return ", ".join(active) if active else ""

    @staticmethod
    def parse_name_and_traits(token):
        name = token
        traits = {'q': False, 'l': False, 'i': False, 'h': False}

        while True:
            changed = False
            for flag, key in [('-q','q'), ('-l','l'), ('-i','i'), ('-h','h')]:
                if name.endswith(flag):
                    traits[key] = True
                    name = name[:-len(flag)]
                    changed = True
            if not changed:
                break
        return name.strip(), traits


class Initiative(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.states = {}

    def get_state(self, ctx):
        gid = ctx.guild.id if ctx.guild else 0
        if gid not in self.states:
            self.states[gid] = InitiativeState()
        return self.states[gid]

    async def _show_initiative(self, ctx, state):
        if not state.current_round:
            await ctx.send("Инициатива пуста. Используйте !f и !di")
            return

        sorted_chars = sorted(
            state.current_round.items(),
            key=lambda x: state.card_value(x[1]['card']),
            reverse=True
        )

        header = f"Раунд {state.round_number}  |  Осталось карт: {len(state.deck)}"
        lines = [header, "-" * len(header)]
        lines.append(f"{'Имя':<20} {'Черты':<28} {'Карта':<12} Все карты")

        for name, data in sorted_chars:
            hold = " (на холде)" if name in state.on_hold else ""
            traits_d = state.get_trait_display(data['traits'])
            card_s = state.format_card(data['card'])
            all_s = state.format_all_cards(data['all_cards'])
            lines.append(f"{name:<20} {traits_d:<28} {card_s:<12} {all_s}{hold}")

        await ctx.send("```\n" + "\n".join(lines) + "\n```")

    def _deal_to_character(self, state, name, traits):
        all_cards = []

        num_draws = 3 if traits.get('i') else 2 if traits.get('l') else 1
        for _ in range(num_draws):
            all_cards.append(state.draw_card())

        best_card = all_cards[0] if all_cards else state.JOKER

        if traits.get('h'):
            if len(all_cards) < 2:
                all_cards.append(state.draw_card())

            jokers = [c for c in all_cards if c == state.JOKER]
            non_jokers = [c for c in all_cards if c != state.JOKER]

            if jokers:
                best_card = state.JOKER
            elif non_jokers:
                best_card = min(non_jokers, key=state.card_value)
            else:
                best_card = state.JOKER

        if traits.get('q') and best_card != state.JOKER:
            curr = state.card_value(best_card)[0]
            while curr <= 3:
                extra = state.draw_card()
                all_cards.append(extra)
                if state.card_value(extra) > state.card_value(best_card):
                    best_card = extra
                if extra == state.JOKER:
                    break
                curr = state.card_value(extra)[0]

        state.current_round[name] = {
            'card': best_card,
            'all_cards': all_cards,
            'traits': traits.copy()
        }

    @commands.command(name='f', aliases=['fight'])
    async def start_fight(self, ctx):
        state = self.get_state(ctx)
        state.deck = state.full_deck()
        random.shuffle(state.deck)
        state.discard = []
        state.current_round = {}
        state.on_hold = set()
        state.joker_this_round = False
        state.round_number = 1
        await ctx.send(f"Бой начат. Новая колода (54 карты). Раунд 1.")

    @commands.command(name='di', aliases=['deal'])
    async def deal_cards(self, ctx, *, names: str):
        state = self.get_state(ctx)

        if not names.strip():
            await ctx.send("Укажите хотя бы одно имя.")
            return

        tokens = names.split()
        dealt = []

        for token in tokens:
            name, traits = InitiativeState.parse_name_and_traits(token)
            if not name: continue

            state.current_round.pop(name, None)
            state.on_hold.discard(name)

            self._deal_to_character(state, name, traits)

            td = state.get_trait_display(traits)
            bc = state.current_round[name]['card']
            dealt.append(f"{name} [{td}]: {state.format_card(bc)}")

        await ctx.send(
            "Карты розданы:\n" + "\n".join(dealt) +
            f"\n\nОсталось в колоде: **{len(state.deck)}** карт"
        )

        await self._show_initiative(ctx, state)

    @commands.command(name='init', aliases=['initiative'])
    async def show_initiative(self, ctx):
        state = self.get_state(ctx)
        await self._show_initiative(ctx, state)

    @commands.command(name='rd', aliases=['round'])
    async def new_round(self, ctx, arg: str = ""):
        state = self.get_state(ctx)
        state.round_number += 1

        keep = '+' in arg.strip()
        removes = {r[1:] for r in re.findall(r'-\w+', arg)}

        to_keep = []

        if keep:
            for name, data in state.current_round.items():
                if name not in removes:
                    to_keep.append((name, data['traits']))
                else:
                    state.on_hold.discard(name)

        state.current_round.clear()
        state.on_hold.clear()

        if state.joker_this_round or len(state.deck) < 10:
            state.shuffle_deck()

        state.joker_this_round = False

        msg = f"Новый раунд {state.round_number}"
        if keep:
            msg += " (персонажи сохранены кроме удалённых)"
        await ctx.send(msg)

        for name, traits in to_keep:
            self._deal_to_character(state, name, traits)

        await self._show_initiative(ctx, state) if state.current_round else \
             ctx.send(f"Инициатива пуста. Осталось карт: {len(state.deck)}")

    @commands.command(name='card')
    async def draw_new_card(self, ctx, *, name: str):
        state = self.get_state(ctx)
        name, _ = InitiativeState.parse_name_and_traits(name)

        if not name or name not in state.current_round:
            await ctx.send("Персонаж не найден")
            return

        traits = state.current_round[name]['traits']
        new_card = state.draw_card()

        state.current_round[name] = {
            'card': new_card,
            'all_cards': [new_card],
            'traits': traits
        }

        await ctx.send(f"{name} тянет новую карту: {state.format_card(new_card)}")
        await self._show_initiative(ctx, state)

    @commands.command(name='drop')
    async def drop_character(self, ctx, *, names: str):
        state = self.get_state(ctx)
        tokens = names.split()
        removed = []

        for token in tokens:
            name, _ = InitiativeState.parse_name_and_traits(token)
            if name in state.current_round:
                del state.current_round[name]
                state.on_hold.discard(name)
                removed.append(name)

        if removed:
            await ctx.send(f"Удалены: {', '.join(removed)}")

        if state.current_round:
            await self._show_initiative(ctx, state)

    @commands.command(name='hold')
    async def hold_action(self, ctx, *, names: str):
        state = self.get_state(ctx)
        tokens = names.split()
        msg = []

        for token in tokens:
            if token.startswith('-'):
                name = token[1:]
                if name in state.on_hold:
                    state.on_hold.discard(name)
                    msg.append(f"Действует: {name}")
            else:
                name, _ = InitiativeState.parse_name_and_traits(token)
                if name in state.current_round:
                    state.on_hold.add(name)
                    msg.append(f"Ожидает: {name}")

        if msg:
            await ctx.send("\n".join(msg))

        if state.current_round:
            await self._show_initiative(ctx, state)


async def setup(bot):
    await bot.add_cog(Initiative(bot))

    await bot.add_cog(Initiative(bot))
