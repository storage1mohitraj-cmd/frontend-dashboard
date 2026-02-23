from typing import Optional, Union

import os
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    
    # Imports to add
    imports_to_add = set()

    # Pattern for "Optional[Type ]" -> "Optional[Type]"
    # This is a simple regex and might need refinement for complex types
    # It handles simple cases like "Optional[int ]", "Optional[str ]", "Optional[List[str] ]"
    
    def repl_optional(match):
        imports_to_add.add('Optional')
        return f"Optional[{match.group(1)}]"
    
    # Regex for "Optional[Type ]" or "Optional[Type]"
    # match.group(1) is the Type
    content = re.sub(r'(?<!Union\[)\b([a-zA-Z0-9_\[\], ]+)\s*\|\s*None\b', repl_optional, content)
    content = re.sub(r'\bNone\s*\|\s*([a-zA-Z0-9_\[\], ]+)\b', repl_optional, content)

    # Pattern for "TypeA | TypeB" -> "Union[TypeA, TypeB]"
    # This targets cases like "int | str", "List[int] | str", etc.
    # We look for typical type hint positions (colon, arrow, or inside [ ])
    def repl_union(match):
        imports_to_add.add('Union')
        type_a = match.group(1).strip()
        type_b = match.group(2).strip()
        return f"Union[{type_a}, {type_b}]"

    # Regex to find TypeA | TypeB that are likely type hints
    # This is still a bit risky but we target patterns like ": TypeA | TypeB" or "-> TypeA | TypeB"
    # or inside other brackets like "List[Union[int, str]]"
    content = re.sub(r'(?<=[:\(,\[])\s*([a-zA-Z0-9_\.\[\] ]+)\s*\|\s*([a-zA-Z0-9_\.\[\] ]+)(?=[\]\),=]|\s*$)', repl_union, content)
    # Also handle return types -> TypeA | TypeB
    content = re.sub(r'(?<=->)\s*([a-zA-Z0-9_\.\[\] ]+)\s*\|\s*([a-zA-Z0-9_\.\[\] ]+)(?=\s*:|\s*$)', repl_union, content)

    if content != original_content:
        # Add imports if missing
        if imports_to_add:
            typing_import = f"from typing import {', '.join(sorted(imports_to_add))}"
            if 'from typing import' in content:
                # Add to existing typing import if it doesn't already have it
                for imp in imports_to_add:
                    if imp not in content:
                        content = re.sub(r'from typing import (.*)', rf'from typing import \1, {imp}', content, count=1)
                        # Clean up any double commas
                        content = content.replace(', ,', ',')
            else:
                # Add a new one
                content = typing_import + "\n" + content
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed {filepath}")
        return True
    return False

def main():
    exclude_dirs = {'venv', 'bot_venv', '__pycache__', '.git'}
    count = 0
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith('.py'):
                if fix_file(os.path.join(root, file)):
                    count += 1
    print(f"Total files fixed: {count}")

if __name__ == '__main__':
    main()
