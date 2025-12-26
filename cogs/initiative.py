from discord.ext import commands
import discord
import random
import re

class Initiative(commands.Cog):
    SUITS = ('♣', '♦', '♥', '♠')
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    JOKER = 'Joker'

    TRAIT_NAMES = {
        'q': 'стремительность',
        'l': 'хладнокровие',
        'i': 'хладнокровие+',  # i и l отображаются одинаково
        'h': 'медлительность'
    }

    def __init__(self, bot):
        self.bot = bot
        self.deck = []
        self.discard = []
        self.current_round = {}  # name → {'card': best, 'all_cards': [...], 'traits': {...}}
        self.on_hold = set()
        self.joker_this_round = False
        self.round_number = 0

    def full_deck(self):
        deck = [f"{rank}{suit}" for suit in self.SUITS for rank in self.RANKS]
        deck += [self.JOKER] * 2
        return deck

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
            return (100, 100)  # Джокер всегда старше всего
        rank = card[:-1]
        rank_idx = self.RANKS.index(rank)
        suit_idx = self.SUITS.index(card[-1])
        return (rank_idx, suit_idx)

    def format_card(self, card):
        if card == self.JOKER:
            return "**Joker**"
        return card

    def format_all_cards(self, cards):
        if not cards:
            return ""
        return "[" + ", ".join(self.format_card(c) for c in cards) + "]"

    def get_trait_display(self, traits):
        active = []
        if traits.get('q'):
            active.append(self.TRAIT_NAMES['q'])
        if traits.get('i') or traits.get('l'):
            active.append(self.TRAIT_NAMES['i'])
        if traits.get('h'):
            active.append(self.TRAIT_NAMES['h'])
        return ", ".join(active) if active else ""

    def parse_name_and_traits(self, token):
        """Парсит токен вида 'Имя-q-l-h' или 'Имя' и возвращает (name, traits_dict)"""
        name = token
        traits = {'q': False, 'l': False, 'i': False, 'h': False}

        while True:
            changed = False
            for flag, key in [('-q', 'q'), ('-l', 'l'), ('-i', 'i'), ('-h', 'h')]:
                if name.endswith(flag):
                    traits[key] = True
                    name = name[:-len(flag)]
                    changed = True
            if not changed:
                break

        return name.strip(), traits

    def deal_to_character(self, name, traits):
        all_cards = []

        # Базовое количество карт
        if traits.get('i'):
            num_draws = 3
        elif traits.get('l'):
            num_draws = 2
        else:
            num_draws = 1

        for _ in range(num_draws):
            all_cards.append(self.draw_card())

        # Медлительность: если h — берём худшую из двух
        if traits.get('h'):
            # Медлительность: всегда тянем две карты
            if len(all_cards) < 2:
                all_cards.append(self.draw_card())

            # Отделяем джокеры
            joker_cards = [c for c in all_cards if c == self.JOKER]
            non_joker_cards = [c for c in all_cards if c != self.JOKER]

            if joker_cards:
                # Джокер всегда остаётся, даже если есть две обычные карты
                best_card = self.JOKER
            else:
                # Нет джокера → берём худшую из обычных
                best_card = min(non_joker_cards, key=self.card_value) if non_joker_cards else self.JOKER

        # Стремительность: если лучшая карта имеет ранг ≤5 (2-5), тянем дальше
        if traits.get('q') and best_card != self.JOKER:
            current_value = self.card_value(best_card)[0]
            while current_value <= 3:  # индексы 0-3 = 2,3,4,5
                extra = self.draw_card()
                all_cards.append(extra)
                if self.card_value(extra) > self.card_value(best_card):
                    best_card = extra
                if extra == self.JOKER:
                    break
                current_value = self.card_value(extra)[0]

        self.current_round[name] = {
            'card': best_card,
            'all_cards': all_cards,
            'traits': traits.copy()
        }

    @commands.command(name='f', aliases=['fight'])
    async def start_fight(self, ctx):
        self.deck = self.full_deck()
        random.shuffle(self.deck)
        self.discard = []
        self.current_round = {}
        self.on_hold = set()
        self.joker_this_round = False
        self.round_number = 1
        remaining = len(self.deck)
        await ctx.send(f"🃏 Бой начат! Новая колода (54 карты), в колоде: **{remaining}** карт. Раунд 1.")

    @commands.command(name='di', aliases=['deal'])
    async def deal_cards(self, ctx, *, names: str):
        if not names.strip():
            await ctx.send("Укажите хотя бы одно имя.")
            return

        tokens = names.split()
        dealt = []

        for token in tokens:
            name, traits = self.parse_name_and_traits(token)
            if not name:
                continue

            # Удаляем старые данные
            self.current_round.pop(name, None)
            self.on_hold.discard(name)

            self.deal_to_character(name, traits)

            trait_display = self.get_trait_display(traits)
            best_card = self.current_round[name]['card']
            dealt.append(f"{name} [{trait_display}]: {self.format_card(best_card)}")

        remaining = len(self.deck)
        await ctx.send("Карты розданы:\n" + "\n".join(dealt) + f"\n\nОсталось в колоде: **{remaining}** карт")

        await self.show_initiative(ctx)

    @commands.command(name='init', aliases=['initiative'])
    async def show_initiative(self, ctx):
        if not self.current_round:
            await ctx.send("Инициатива пуста. Используйте `!f` и `!di`.")
            return

        sorted_chars = sorted(
            self.current_round.items(),
            key=lambda x: self.card_value(x[1]['card']),
            reverse=True
        )

        remaining = len(self.deck)
        header = f" ========== Раунд {self.round_number} | В колоде: {remaining} карт ========== "
        lines = [header]
        lines.append(f"{'Имя':<20} {'Черты':<28} {'Карта':<12} Все карты")

        for name, data in sorted_chars:
            hold = " (на холде)" if name in self.on_hold else ""
            traits_display = self.get_trait_display(data['traits'])
            card_str = self.format_card(data['card'])
            all_str = self.format_all_cards(data['all_cards'])
            line = f"{name:<20} {traits_display:<28} {card_str:<12} {all_str}{hold}"
            lines.append(line)

        await ctx.send("```\n" + "\n".join(lines) + "\n```")

    @commands.command(name='rd', aliases=['round'])
    async def new_round(self, ctx, arg: str = ""):
        self.round_number += 1

        keep = '+' in arg.strip()  # игнорируем лишние пробелы
        removes = re.findall(r'-\w+', arg)
        remove_names = {r[1:] for r in removes}

        characters_to_keep = []

        if keep:
            # Сохраняем всех, кроме явно удалённых через -Имя
            for name, data in self.current_round.items():
                if name not in remove_names:
                    characters_to_keep.append((name, data['traits']))
                else:
                    # Опционально: снимаем с холда удаляемых
                    self.on_hold.discard(name)
        else:
            # Без + — никого не сохраняем
            pass

        # Очищаем текущий раунд и холд
        self.current_round.clear()
        self.on_hold.clear()

        # Пересдаём колоду, если был джокер или мало карт
        if self.joker_this_round or len(self.deck) < 10:
            self.shuffle_deck()

        self.joker_this_round = False

        msg = f"🕐 Новый раунд {self.round_number}!"
        if keep:
            msg += " Персонажи с чертами сохранены (кроме удалённых)."
        await ctx.send(msg)

        # Перераздаём сохранённым
        if characters_to_keep:
            for name, traits in characters_to_keep:
                self.deal_to_character(name, traits)

        if self.current_round:
            await self.show_initiative(ctx)
        else:
            remaining = len(self.deck)
            await ctx.send(f"Инициатива пуста. Осталось в колоде: **{remaining}** карт")

    @commands.command(name='card')
    async def draw_new_card(self, ctx, *, name: str):
        name, _ = self.parse_name_and_traits(name)  # на случай если с флагами
        if not name or name not in self.current_round:
            await ctx.send("Персонаж не найден.")
            return

        traits = self.current_round[name]['traits']
        new_card = self.draw_card()

        self.current_round[name] = {
            'card': new_card,
            'all_cards': [new_card],
            'traits': traits
        }

        await ctx.send(f"{name} тянет новую карту: {self.format_card(new_card)}")
        await self.show_initiative(ctx)

    @commands.command(name='drop')
    async def drop_character(self, ctx, *, names: str):
        tokens = names.split()
        removed = []
        for token in tokens:
            name, _ = self.parse_name_and_traits(token)
            if name in self.current_round:
                del self.current_round[name]
                self.on_hold.discard(name)
                removed.append(name)
        if removed:
            await ctx.send(f"Удалены: {', '.join(removed)}")
        if self.current_round:
            await self.show_initiative(ctx)

    @commands.command(name='hold')
    async def hold_action(self, ctx, *, names: str):
        tokens = names.split()
        msg = []
        for token in tokens:
            if token.startswith('-'):
                name = token[1:]
                if name in self.on_hold:
                    self.on_hold.discard(name)
                    msg.append(f"Действует: {name}")
            else:
                name, _ = self.parse_name_and_traits(token)
                if name in self.current_round:
                    self.on_hold.add(name)
                    msg.append(f"Ожидает: {name}")
        if msg:
            await ctx.send("\n".join(msg))
        if self.current_round:
            await self.show_initiative(ctx)


async def setup(bot):
    await bot.add_cog(Initiative(bot))