"""
Restore original footer text across all cogs EXCEPT playerinfo.py.

Strategy:
For each target file, find every set_footer() call that currently contains
"Whiteout Survival | Magnus". For each such block, find the closest matching
block (by line number) in the old reference file and use that text instead.
If no old match is found, skip that block.
"""

import re
import os

BASE_DIR = r"F:\Whiteout Survival Bot"
COGS_DIR = os.path.join(BASE_DIR, "DISCORD BOT", "cogs")
OLD_DIR  = os.path.join(BASE_DIR, "tmp_restore")

BRANDING = 'Whiteout Survival | Magnus'

FILES = {
    "attendance.py":         "old_attendance.py",
    "attendance_report.py":  "old_attendance_report.py",
    "bear_trap_editor.py":   "old_bear_trap_editor.py",
    "changes.py":            "old_changes.py",
    "control.py":            "old_control.py",
    "fid_commands.py":       "old_fid_commands.py",
    "gift_operationsapi.py": "old_gift_operationsapi.py",
    "message_extractor.py":  "old_message_extractor.py",
    "minister_menu.py":      "old_minister_menu.py",
    "pagination_helper.py":  "old_pagination_helper.py",
    "personalise_chat.py":   "old_personalise_chat.py",
    "player_id_validator.py":"old_player_id_validator.py",
    "remote_access.py":      "old_remote_access.py",
    "support_operations.py": "old_support_operations.py",
    "shared_views.py":       "old_shared_views.py",
    "start_menu.py":         "old_start_menu.py",
    "welcome_channel.py":    "old_welcome_channel.py",
}


def extract_footer_blocks(lines):
    """
    Returns list of (start_idx, end_idx, joined_text) for each set_footer() call.
    Handles single-line and multi-line parenthesised calls.
    """
    blocks = []
    i = 0
    while i < len(lines):
        if 'set_footer(' in lines[i]:
            start = i
            depth = lines[i].count('(') - lines[i].count(')')
            j = i
            while depth > 0 and j + 1 < len(lines):
                j += 1
                depth += lines[j].count('(') - lines[j].count(')')
            text = '\n'.join(lines[start:j+1])
            blocks.append((start, j, text))
            i = j + 1
        else:
            i += 1
    return blocks


def get_leading_spaces(line):
    return len(line) - len(line.lstrip(' '))


def reindent(block_lines, target_indent, source_indent):
    """Adjust indentation of a block to match target."""
    result = []
    for ln in block_lines:
        stripped = ln.lstrip(' ')
        current = len(ln) - len(stripped)
        # relative indentation within block
        rel = current - source_indent
        new_indent = max(0, target_indent + rel)
        result.append(' ' * new_indent + stripped)
    return result


def process_file(cur_path, old_path):
    with open(cur_path, 'r', encoding='utf-8') as f:
        cur_lines = [l.rstrip('\n') for l in f.readlines()]

    with open(old_path, 'r', encoding='utf-8') as f:
        old_lines = [l.rstrip('\n') for l in f.readlines()]

    cur_blocks = extract_footer_blocks(cur_lines)
    old_blocks = extract_footer_blocks(old_lines)

    # Only work on current blocks that have the branding text
    targets = [(s, e, t) for (s, e, t) in cur_blocks if BRANDING in t]

    if not targets:
        print(f"  [SKIP] No branding footers found")
        return False

    if not old_blocks:
        print(f"  [WARN] Old file has no footer blocks — skipping")
        return False

    # For each target branding block, find the closest old block by line number
    old_starts = [s for (s, e, t) in old_blocks]

    new_lines = list(cur_lines)
    offset = 0
    changes = 0

    for (cs, ce, ct) in targets:
        adj_cs = cs + offset
        adj_ce = ce + offset

        # Find closest old block by start line proximity
        best_idx = min(range(len(old_blocks)), key=lambda i: abs(old_blocks[i][0] - cs))
        os_, oe_, ot_ = old_blocks[best_idx]

        old_block_lines = old_lines[os_:oe_+1]
        src_indent = get_leading_spaces(old_block_lines[0])
        tgt_indent = get_leading_spaces(new_lines[adj_cs])

        aligned = reindent(old_block_lines, tgt_indent, src_indent)

        new_lines[adj_cs:adj_ce+1] = aligned

        shift = len(aligned) - (adj_ce - adj_cs + 1)
        offset += shift
        changes += 1
        print(f"  [OK] Line ~{cs+1}: restored -> {ot_.strip()[:90]}")

    if changes:
        with open(cur_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(new_lines))
        print(f"  => Saved {changes} change(s)")

    return changes > 0


def main():
    total = 0
    for cur_name, old_name in FILES.items():
        cur_path = os.path.join(COGS_DIR, cur_name)
        old_path = os.path.join(OLD_DIR,  old_name)

        if not os.path.exists(cur_path):
            print(f"[MISSING current] {cur_name}")
            continue
        if not os.path.exists(old_path):
            print(f"[MISSING old] {old_name}")
            continue

        print(f"\nProcessing: {cur_name}")
        try:
            if process_file(cur_path, old_path):
                total += 1
        except Exception as ex:
            print(f"  [ERROR] {ex}")

    print(f"\n=== Done. Modified {total} file(s). ===")


if __name__ == "__main__":
    main()
