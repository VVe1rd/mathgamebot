import discord
from discord.ext import commands, tasks
from itertools import cycle
import random
import asyncio
from IPython.display import Image, display
import pydotplus

def read_token():
    with open("token.txt", "r") as f:
        lines = f.readlines()
        return lines[0].strip()

def read_channel_id():
    with open("channel.txt", "r") as f:
        lines = f.readlines()
        return lines[0].strip()

token = read_token()
channel_id = int(read_channel_id())
version = 1009

class Player():
    def __init__(self, id, gold, user):
        self.id = id
        self.gold = gold
        self.user = user
        self.target = 0
        self.thieves = []
        self.vote = 3

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.players = []
        self.state = 'none'
        self.day = 0
        self.max_day = 3
        self.day_left_bound = 1
        self.day_right_bound = 10

    async def on_ready(self):
        print('Logged in as')
        print(self.user.name)
        print(self.user.id)
        print('------')

    async def game_over(self):
        channel = self.get_channel(channel_id)
        self.state = 'none'
        self.day = 0
        await self.gold_exchange()
        winners = []
        max_gold = 0
        for elem in self.players:
            if elem.gold > max_gold:
                max_gold = elem.gold
        for elem in self.players:
            if elem.gold == max_gold:
                winners.append(elem)
        await channel.send('Игра окончена!')
        for elem in self.players:
            await channel.send(str(elem.id) + ') ' + '{}'.format(elem.user.mention) + ' - ' + str(elem.gold))
        if len(winners) > 1:
            await channel.send('Победители:')
            for elem in winners:
                await channel.send('{}'.format(elem.user.mention))
        else:
            await channel.send('Победитель: {}!'.format(winners[0].user.mention))
        self.players = []

    async def gold_exchange(self):
        channel = self.get_channel(channel_id)

        for elem in self.players:
            if len(elem.thieves) > 0:
                elem.gold = elem.gold // 2

        incomes = []
        for i in range(len(self.players)):
            incomes.append(0)

        for i in range(len(self.players)):
            for thief in self.players[i].thieves:
                incomes[thief.id - 1] = self.players[i].gold // len(self.players[i].thieves)

        for i in range(len(self.players)):
            self.players[i].gold += incomes[i]

        graph = pydotplus.Dot(graph_type="digraph")
        for elem in self.players:
            node = pydotplus.Node(elem.user.name, style="filled", fillcolor="blue")
            graph.add_node(node)
        for elem in self.players:
            for thief in elem.thieves:
                edge = pydotplus.Edge(thief.user.name, elem.user.name)
                graph.add_edge(edge)
        graph.write_png('day' + str(self.day) + '.png')
        await channel.send(file=discord.File('day' + str(self.day) + '.png'))

        for elem in self.players:
            elem.thieves = []

    async def change_phase(self):
        await self.wait_until_ready()
        channel = self.get_channel(channel_id)
        while not self.is_closed():
            self.day += 1
            if self.day > self.max_day:
                await self.game_over()
                return
            await self.gold_exchange()
            await channel.send('День ' + str(self.day) + '/' + str(self.max_day))
            for elem in self.players:
                player_state = str(elem.id) + ') ' + '{}'.format(elem.user.mention) + ' - ' + str(elem.gold)
                if self.day > 1:
                    player_state += ' (выбрал ' + str(elem.target) + ')'
                await channel.send(player_state)
            for elem in self.players:
                elem.target = 0
            await asyncio.sleep(30)
            await channel.send('Осталось 30 секунд...')
            await asyncio.sleep(30)

    async def get_player(self, message: discord.Message):
        for elem in self.players:
            if elem.user.id == message.author.id:
                return elem

    async def on_message(self, message):
        channel = self.get_channel(channel_id)

        if message.content == '!version':
            await channel.send(file=discord.File('test.jpg'))
            await channel.send(str(version))
            return

        if message.channel == channel:
            if message.author.id == self.user.id:
                return

            elif message.content == '!start' and self.state == 'none':
                self.state = 'ready'
                await channel.send('Присоединяйтесь к игре командой !play')
                await channel.send('Игра начнется через одну минуту...')
                await asyncio.sleep(30)
                await channel.send('Осталось 30 секунд до начала игры... Успевайте присоединиться!')
                await asyncio.sleep(30)
                self.state = 'game'
                self.max_day = 0
                for elem in self.players:
                    self.max_day += elem.vote
                self.max_day = self.max_day // len(self.players)
                await channel.send('Игра началась!')
                self.loop.create_task(self.change_phase())

            elif message.content == '!play' and self.state == 'ready':
                player = Player(len(self.players) + 1, 1000, message.author)
                self.players.append(player)
                await channel.send('{0.author.mention} присоединился к игре!'.format(message))

            elif message.content.startswith('!vote ') and self.state == 'ready':
                await self.vote(message)

            elif message.content.startswith('!graph ') and self.state == 'game':
                await self.show_graph(message)

        elif message.guild is None:
            if self.state == 'game':
                author = await self.get_player(message)
                if author is None:
                    return
                if author.target > 0:
                    await message.author.send('Вы уже выбрали жертву.')
                    return
                if message.content.isdigit():
                    if 1 <= int(message.content) <= len(self.players):
                        if int(message.content) == author.id:
                            await message.author.send('Вы не можете выбрать себя! Попробуйте еще раз')
                            return
                        author.target = int(message.content)
                        self.players[author.target - 1].thieves.append(author)
                        await message.author.send('Вы выбрали {} в качестве жертвы.'.format(self.players[author.target - 1].user.name))
                    else:
                        await message.author.send('Неправильный ID игрока! Попробуйте еще раз.')

    async def vote(self, message: discord.Message):
        channel = self.get_channel(channel_id)
        lhs, rhs = message.content.split(" ", 1)
        if rhs.isdigit():
            if self.day_left_bound <= int(rhs) <= self.day_right_bound:
                author = await self.get_player(message)
                if author is None:
                    return
                author.vote = int(rhs)
                await channel.send('{}, голос засчитан!'.format(message.author.mention))
            else:
                await channel.send('{}, число не входит в диапазон!'.format(message.author.mention))

    async def show_graph(self, message: discord.Message):
        channel = self.get_channel(channel_id)
        lhs, rhs = message.content.split(" ", 1)
        if rhs.isdigit():
            if 1 <= int(rhs) <= self.day:
                await channel.send(file=discord.File('day' + rhs + '.png'))

client = MyClient()
client.run(token)
