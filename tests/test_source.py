import ast
from pathlib import Path


def test_python_sources_parse():
    for path in Path('bot').rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))


def test_no_literal_discord_token_in_source():
    for path in Path('bot').rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        assert 'bot.run(' not in text
        assert 'MTAxMzg1' not in text
