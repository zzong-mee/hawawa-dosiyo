"""Korean display names for Discord application commands."""

import discord
from discord import app_commands

COMMAND_NAMES = {
    "ping": "핑", "help": "도움말", "serverinfo": "서버정보", "userinfo": "사용자정보", "timezone": "시간대", "create": "생성", "list": "목록", "delete": "삭제",
    "South Korea": "한국", "Japan": "일본", "China": "중국", "Singapore": "싱가포르", "India": "인도", "United Kingdom": "영국", "France": "프랑스", "Germany": "독일", "US Eastern": "미국 동부", "US Pacific": "미국 서부", "Canada Eastern": "캐나다 동부", "Australia Eastern": "호주 동부", "Brazil": "브라질",
    "avatar": "아바타", "roll": "주사위", "vote": "랜덤선택", "poll": "투표",
    "randomteam": "랜덤팀", "clear": "청소", "charinfo": "문자정보", "permissions": "권한",
    "tag": "태그", "welcome": "환영설정", "autorole": "자동역할", "reminder": "알림",
    "rolepanel": "역할패널", "rolepaneldisable": "역할패널해제", "serverconfig": "서버설정",
    "suggest": "건의", "rank": "내레벨", "leaderboard": "레벨순위", "automod": "자동관리",
    "temprole": "기간역할", "giveaway": "추첨", "starboard": "추천게시판",
    "modcase": "관리기록", "trigger": "자동응답", "embed": "안내임베드",
    "roleautomation": "역할자동화", "coinflip": "동전던지기", "rps": "가위바위보",
    "members": "멤버목록", "greetingtemplate": "안내문구", "sticky": "고정안내",
    "suggestion": "건의관리", "levelreward": "레벨보상", "stocks": "주식시세",
    "stockbuy": "주식매수", "stocksell": "주식매도", "portfolio": "내주식",
}

OPTION_NAMES = {
    "command": "명령어", "user": "사용자", "global_avatar": "계정아바타", "sides": "면수",
    "count": "개수", "options": "선택지", "participants": "참가자", "teams": "팀수",
    "characters": "문자", "member": "멤버", "bot": "봇", "action": "동작",
    "name": "이름", "content": "내용", "channel": "채널", "disable": "해제",
    "role": "역할", "minutes": "분", "text": "문구", "reminder_id": "알림번호",
    "repeat_minutes": "반복간격", "alert": "시간", "timer": "타이머", "mode": "방식", "title": "제목", "feature": "기능", "enabled": "활성화",
    "kind": "종류", "words": "단어", "mentions": "멘션수", "prize": "경품",
    "winners": "당첨자수", "message_id": "메시지번호", "minimum": "최소반응수",
    "reason": "사유", "keyword": "키워드", "response": "응답", "level": "레벨",
    "choice": "선택", "order": "정렬기준", "symbol": "종목", "quantity": "수량", "mode": "방식",
}


class KoreanTranslator(app_commands.Translator):
    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context):
        if locale is discord.Locale.korean:
            return COMMAND_NAMES.get(string.message) or OPTION_NAMES.get(string.message)
        return None
