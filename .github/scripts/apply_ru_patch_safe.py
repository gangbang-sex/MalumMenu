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

# Touch only C# string literals. For interpolated strings ($"...{expr}..."),
# translate only visible text and preserve all C# expressions inside {...}.
string_literal = re.compile(r'(?P<prefix>\$?)"(?P<body>(?:\\.|[^"\\])*)"')
ordered = sorted(translations.items(), key=lambda item: len(item[0]), reverse=True)

changed_files = 0
changed_literals = 0


def translate_text(text: str) -> str:
    for english, russian in ordered:
        text = text.replace(english, russian)
    return text


def translate_interpolated_body(body: str) -> str:
    out = []
    visible = []
    i = 0
    n = len(body)

    def flush_visible():
        if visible:
            out.append(translate_text(''.join(visible)))
            visible.clear()

    while i < n:
        ch = body[i]

        # Escaped literal braces in interpolated strings: {{ and }}.
        if ch == '{' and i + 1 < n and body[i + 1] == '{':
            visible.append('{{')
            i += 2
            continue
        if ch == '}' and i + 1 < n and body[i + 1] == '}':
            visible.append('}}')
            i += 2
            continue

        if ch != '{':
            visible.append(ch)
            i += 1
            continue

        # Start of an interpolation expression. Preserve it byte-for-byte.
        flush_visible()
        start = i
        depth = 0
        in_string = False
        escaped = False

        while i < n:
            c = body[i]
            if in_string:
                if escaped:
                    escaped = False
                elif c == '\\':
                    escaped = True
                elif c == '"':
                    in_string = False
            else:
                if c == '"':
                    in_string = True
                elif c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
            i += 1

        out.append(body[start:i])

    flush_visible()
    return ''.join(out)


for path in Path('src').rglob('*.cs'):
    text = path.read_text(encoding='utf-8-sig')
    original = text

    def translate_literal(match):
        global changed_literals
        prefix = match.group('prefix')
        body = match.group('body')
        new_body = translate_interpolated_body(body) if prefix == '$' else translate_text(body)
        if new_body != body:
            changed_literals += 1
        return f'{prefix}\"{new_body}\"'

    text = string_literal.sub(translate_literal, text)
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed_files += 1

if changed_files == 0:
    raise SystemExit('RU patch did not change any C# source files')

print(f'Russian UI patch applied safely to {changed_files} C# files ({changed_literals} string literals)')
