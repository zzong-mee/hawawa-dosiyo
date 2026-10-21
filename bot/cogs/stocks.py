"""Persistent virtual stock market mini-game."""

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from bot.presentation import add_lines, make_embed
from bot.storage import Store

STOCKS = {
    "HAWA": ("하와와 테크", 120),
    "DOSI": ("도시요 엔터테인먼트", 85),
    "TAKO": ("타코야키 푸드", 60),
    "MINE": ("마인코드 게임즈", 150),
}
Symbol = Literal["HAWA", "DOSI", "TAKO", "MINE"]


class Stocks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = Store()

    async def ensure_market(self, guild_id: int, user_id: int):
        await self.store.execute(
            "INSERT OR IGNORE INTO stock_accounts(guild,user,cash) VALUES(?,?,10000)",
            (guild_id, user_id),
        )
        for symbol, (_, price) in STOCKS.items():
            await self.store.execute(
                "INSERT OR IGNORE INTO stock_market(guild,symbol,price) VALUES(?,?,?)",
                (0, symbol, price),
            )

    async def price(self, guild_id, symbol):
        rows = await self.store.execute("SELECT price FROM stock_market WHERE guild=0 AND symbol=?", (symbol,))
        return rows[0][0] if rows else STOCKS[symbol][1]

    @app_commands.command(name="stocks", description="가상 주식 시장의 현재 시세를 확인합니다.")
    @app_commands.guild_only()
    async def stocks(self, interaction: discord.Interaction):
        await self.ensure_market(interaction.guild.id, interaction.user.id)
        rows = await self.store.execute("SELECT symbol,price FROM stock_market WHERE guild=0 ORDER BY symbol")
        lines = [f"**{symbol}** · {STOCKS[symbol][0]}\n💰 **{price:,}** 코인" for symbol, price in rows]
        embed = make_embed(title="가상 주식 시장", description="모든 서버가 같은 공용 시세를 사용합니다. 시작 자금은 10,000 코인이에요.", kind="social")
        add_lines(embed, "종목 · 현재가", lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="stockbuy", description="가상 주식을 매수합니다.")
    @app_commands.guild_only()
    @app_commands.describe(symbol="매수할 종목", mode="매수 방식", quantity="수량 지정 시 매수 수량")
    async def stockbuy(self, interaction: discord.Interaction, symbol: Symbol, mode: Literal["수량 지정", "풀매수"] = "수량 지정", quantity: app_commands.Range[int, 1, 10000] = 1):
        await self.ensure_market(interaction.guild.id, interaction.user.id)
        price = await self.price(interaction.guild.id, symbol)
        rows = await self.store.execute("SELECT cash FROM stock_accounts WHERE guild=? AND user=?", (interaction.guild.id, interaction.user.id))
        cash = rows[0][0]
        if mode == "풀매수":
            quantity = cash // price
        total = price * quantity
        if quantity < 1:
            await interaction.response.send_message("보유 코인으로 매수할 수 있는 주식이 없습니다.", ephemeral=True)
            return
        if cash < total:
            await interaction.response.send_message(f"잔액이 부족합니다. 필요 **{total:,}** · 보유 **{cash:,}** 코인", ephemeral=True)
            return
        await self.store.execute("UPDATE stock_accounts SET cash=cash-? WHERE guild=? AND user=?", (total, interaction.guild.id, interaction.user.id))
        await self.store.execute("INSERT INTO stock_holdings VALUES(?,?,?,?) ON CONFLICT(guild,user,symbol) DO UPDATE SET quantity=quantity+excluded.quantity", (interaction.guild.id, interaction.user.id, symbol, quantity))
        label = "풀매수" if mode == "풀매수" else f"{quantity:,}주 매수"
        await interaction.response.send_message(f"📈 **{STOCKS[symbol][0]}** {label} · **{total:,}** 코인", ephemeral=True)

    @app_commands.command(name="stocksell", description="보유한 가상 주식을 매도합니다.")
    @app_commands.guild_only()
    @app_commands.describe(symbol="매도할 종목", mode="매도 방식", quantity="수량 지정 시 매도 수량")
    async def stocksell(self, interaction: discord.Interaction, symbol: Symbol, mode: Literal["수량 지정", "풀매도"] = "수량 지정", quantity: app_commands.Range[int, 1, 10000] = 1):
        await self.ensure_market(interaction.guild.id, interaction.user.id)
        rows = await self.store.execute("SELECT quantity FROM stock_holdings WHERE guild=? AND user=? AND symbol=?", (interaction.guild.id, interaction.user.id, symbol))
        owned = rows[0][0] if rows else 0
        if mode == "풀매도":
            quantity = owned
        if owned < quantity:
            await interaction.response.send_message(f"보유 수량이 부족합니다. 보유 **{owned:,}**주", ephemeral=True)
            return
        price = await self.price(interaction.guild.id, symbol)
        total = price * quantity
        await self.store.execute("UPDATE stock_holdings SET quantity=quantity-? WHERE guild=? AND user=? AND symbol=?", (quantity, interaction.guild.id, interaction.user.id, symbol))
        await self.store.execute("UPDATE stock_accounts SET cash=cash+? WHERE guild=? AND user=?", (total, interaction.guild.id, interaction.user.id))
        label = "풀매도" if mode == "풀매도" else f"{quantity:,}주 매도"
        await interaction.response.send_message(f"📉 **{STOCKS[symbol][0]}** {label} · **{total:,}** 코인", ephemeral=True)

    @app_commands.command(name="portfolio", description="내 가상 자산과 보유 주식을 확인합니다.")
    @app_commands.guild_only()
    async def portfolio(self, interaction: discord.Interaction):
        await self.ensure_market(interaction.guild.id, interaction.user.id)
        cash = (await self.store.execute("SELECT cash FROM stock_accounts WHERE guild=? AND user=?", (interaction.guild.id, interaction.user.id)))[0][0]
        rows = await self.store.execute("SELECT symbol,quantity FROM stock_holdings WHERE guild=? AND user=? AND quantity>0 ORDER BY symbol", (interaction.guild.id, interaction.user.id))
        total = cash
        lines = []
        for symbol, quantity in rows:
            value = quantity * await self.price(interaction.guild.id, symbol)
            total += value
            lines.append(f"**{symbol}** · {STOCKS[symbol][0]} · {quantity:,}주 · **{value:,}** 코인")
        embed = make_embed(title="내 주식 포트폴리오", description=f"💰 현금 **{cash:,}** 코인\n📊 총 평가액 **{total:,}** 코인", kind="info")
        add_lines(embed, "보유 종목", lines or ["보유 중인 주식이 없습니다."])
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stocks(bot))
