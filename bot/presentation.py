"""Shared Discord cards and safe, human-readable entity labels."""

import asyncio

import discord

COLORS = {"info": 0x8B5CF6, "success": 0x10B981, "warning": 0xF59E0B, "danger": 0xF43F5E, "social": 0x06B6D4}
ICONS = {
    "사용자 정보": "👤", "아바타": "🖼️", "서버 정보": "🏰", "문자 정보": "🔎",
    "현재 채널 권한": "🛡️", "랜덤 팀 배정": "🎲", "관리 기록": "📋",
    "Hawawa Dosiyo 명령어": "✨", "새 건의": "💡", "참가자 추첨": "🎁",
    "추첨 마감": "🏆", "퇴장 안내": "👋", "경험치 순위": "🏅", "경험치 프로필": "🌟",
    "멤버 입장": "📥", "멤버 퇴장": "📤", "채널 생성": "🆕", "채널 삭제": "🗑️",
    "역할 생성": "🎭", "역할 삭제": "🗑️",
}


def text_name(entity, fallback="이름을 확인할 수 없는 사용자"):
    for attribute in ("display_name", "name"):
        value = getattr(entity, attribute, None)
        if isinstance(value, str) and value.strip():
            value = value.replace("\n", " ").replace("\r", " ")
            return discord.utils.escape_markdown(discord.utils.escape_mentions(value))[:80]
    return fallback


def channel_name(guild, identifier):
    getter = getattr(guild, "get_channel_or_thread", None) or getattr(guild, "get_channel", None)
    channel = getter(int(identifier)) if getter else None
    return "#" + text_name(channel, "이름 없음") if channel else "삭제되었거나 접근할 수 없는 채널"


def role_name(guild, identifier):
    getter = getattr(guild, "get_role", None)
    role = getter(int(identifier)) if getter else None
    return text_name(role, "이름 없는 역할") if role else "삭제된 역할"


async def user_names(guild, identifiers, bot=None, known=()):
    """Resolve each unique user once; never fall back to a numeric mention."""
    known = {entity.id: entity for entity in known if entity is not None}
    limit = asyncio.Semaphore(4)

    async def resolve(identifier):
        member_getter = getattr(guild, "get_member", None)
        member = known.get(identifier) or (member_getter(identifier) if member_getter else None)
        if member is not None:
            return identifier, text_name(member)
        async with limit:
            fetch = getattr(guild, "fetch_member", None)
            if fetch:
                try:
                    member = await asyncio.wait_for(fetch(identifier), timeout=3)
                    return identifier, text_name(member)
                except (discord.HTTPException, asyncio.TimeoutError, OSError):
                    pass
            getter = getattr(bot, "get_user", None)
            user = getter(identifier) if getter else None
            return identifier, text_name(user, "탈퇴했거나 이름을 확인할 수 없는 사용자")

    return dict(await asyncio.gather(*(resolve(int(identifier)) for identifier in set(identifiers))))


def make_embed(*, title=None, description=None, color=None, kind="info"):
    icon = ICONS.get(title)
    if icon:
        title = f"{icon} {title}"
    embed = discord.Embed(
        title=title, description=description,
        color=color if color is not None else COLORS[kind], timestamp=discord.utils.utcnow(),
    )
    embed.set_author(name="HAWAWA DOSIYO")
    embed.set_footer(text="Hawawa Dosiyo · 함께 만드는 즐거운 서버")
    return embed


def identify(embed, entity):
    """Put a readable name and optional avatar in the card header."""
    avatar = getattr(getattr(entity, "display_avatar", None), "url", None)
    options = {"icon_url": avatar} if isinstance(avatar, str) else {}
    embed.set_author(name=text_name(entity), **options)


def add_lines(embed, name, lines, *, inline=False):
    """Keep full lines while respecting Discord's 1024-character field limit."""
    chunk = []
    continuation = False
    for line in lines:
        if chunk and len("\n".join(chunk + [line])) > 1000:
            embed.add_field(name=name + (" · 계속" if continuation else ""), value="\n".join(chunk), inline=inline)
            chunk = []
            continuation = True
        chunk.append(line)
    if chunk:
        embed.add_field(name=name + (" · 계속" if continuation else ""), value="\n".join(chunk), inline=inline)
