"""Direct-mention AI replies; passive unless explicitly enabled."""

import logging
import re

import discord
from discord.ext import commands

from bot.ai.character import character_prompt
from bot.ai.client import OllamaClient, OllamaError

logger = logging.getLogger("hawawa.ai_chat")
MAX_REPLY_LENGTH = 2000


def mention_prompt(message: discord.Message, bot_user: discord.ClientUser) -> str | None:
    if message.guild is None or message.author.bot or message.webhook_id:
        return None
    if bot_user not in message.mentions:
        return None
    content = re.sub(rf"<@!?{bot_user.id}>", "", message.content).strip()
    return content or "짧게 자연스럽게 인사해줘."


def safe_reply(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "지금은 답변을 만들지 못했어. 잠시 후 다시 말해줘!"
    return cleaned[:MAX_REPLY_LENGTH]


class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = OllamaClient()

    def cog_unload(self):
        self.bot.loop.create_task(self.client.aclose())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        prompt = mention_prompt(message, self.bot.user)
        if prompt is None:
            return
        try:
            async with message.channel.typing():
                response = await self.client.generate(prompt, system=character_prompt())
            await message.reply(safe_reply(response), mention_author=False, allowed_mentions=discord.AllowedMentions.none())
        except OllamaError:
            await message.reply("지금 AI 응답을 준비하지 못했어. 잠시 후 다시 시도해줘!", mention_author=False, allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            logger.exception("AI mention response failed")
            await message.reply("잠깐 문제가 생겼어. 조금 뒤에 다시 말해줘!", mention_author=False, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: commands.Bot):
    await bot.add_cog(AIChat(bot))
