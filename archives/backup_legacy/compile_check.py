
import traceback
import sys

try:
    with open('app.py', encoding='utf-8') as f:
        content = f.read()
    compile(content, 'app.py', 'exec')
    print('SUCCESS')
except SyntaxError as e:
    print(f"SyntaxError at line {e.lineno}, offset {e.offset}: {e.text}")
    print(f"Error detail: {e}")
except Exception as e:
    traceback.print_exc()
