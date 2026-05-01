from admin_utils import format_furnace_level

def test():
    test_cases = [
        (30, "30"),
        (31, "FC 1-1"),
        (34, "FC 1-4"),
        (35, "FC 1"),
        (36, "FC 2-1"),
        (40, "FC 2"),
        (43, "FC 3-3"),
        (45, "FC 3"),
    ]
    
    for lv, expected in test_cases:
        result = format_furnace_level(lv)
        print(f"Level {lv}: {result} (Expected: {expected})")
        assert result == expected

if __name__ == "__main__":
    test()
