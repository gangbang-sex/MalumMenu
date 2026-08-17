from pathlib import Path
import ast
import re

SOURCE_PATCHER = Path('.github/scripts/apply_ru_patch.py')

# Reuse the translation dictionary without executing the original patcher.
tree = ast.parse(SOURCE_PATCHER.read_text(encoding='utf-8'))
translations = None
for node in tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'translations':
                translations = ast.literal_eval(node.value)
                break
    if translations is not None:
        break

if not isinstance(translations, dict):
    raise SystemExit('Could not load translations dictionary')

# Only touch C# string literals. This keeps class/method/field identifiers intact.
# Covers normal and interpolated strings used by MalumMenu UI code.
string_literal = re.compile(r'(?P<prefix>\$?)"(?P<body>(?:\\.|[^"\\])*)"')
ordered = sorted(translations.items(), key=lambda item: len(item[0]), reverse=True)

changed_files = 0
changed_literals = 0

for path in Path('src').rglob('*.cs'):
    text = path.read_text(encoding='utf-8-sig')
    original = text

    def translate_literal(match):
        nonlocal_holder = None
        body = match.group('body')
        new_body = body
        for english, russian in ordered:
            new_body = new_body.replace(english, russian)
        if new_body != body:
            global changed_literals
            changed_literals += 1
        return f'{match.group("prefix")}\"{new_body}\"'

    text = string_literal.sub(translate_literal, text)
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed_files += 1

if changed_files == 0:
    raise SystemExit('RU patch did not change any C# source files')

print(f'Russian UI patch applied safely to {changed_files} C# files ({changed_literals} string literals)')
