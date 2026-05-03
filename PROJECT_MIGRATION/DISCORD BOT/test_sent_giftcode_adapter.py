"""
Test script for the robust SentGiftCodesAdapter MongoDB integration.
This verifies that gift codes are properly tracked and not duplicated.
"""

import sys
import os
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from db.mongo_adapters import mongo_enabled, SentGiftCodesAdapter
    print("✅ Successfully imported SentGiftCodesAdapter")
except ImportError as e:
    print(f"❌ Failed to import: {e}")
    sys.exit(1)


def test_basic_operations():
    """Test basic CRUD operations"""
    print("\n" + "="*60)
    print("Testing Basic Operations")
    print("="*60)
    
    if not mongo_enabled():
        print("⚠️ MongoDB not enabled (MONGO_URI not set)")
        return False
    
    test_guild_id = 999999999  # Test guild ID
    test_codes = ['TESTCODE1', 'TESTCODE2', 'testcode3']  # Mixed case
    
    # 1. Clear any existing test data
    print("\n1. Clearing test data...")
    SentGiftCodesAdapter.clear_guild_codes(test_guild_id)
    
    # 2. Mark codes as sent
    print(f"\n2. Marking {len(test_codes)} codes as sent...")
    success = SentGiftCodesAdapter.mark_codes_sent(
        guild_id=test_guild_id,
        codes=test_codes,
        source='test'
    )
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # 3. Retrieve sent codes
    print("\n3. Retrieving sent codes...")
    sent_codes = SentGiftCodesAdapter.get_sent_codes(test_guild_id)
    print(f"   Retrieved {len(sent_codes)} codes: {sent_codes}")
    
    # 4. Check if specific code was sent (case insensitive)
    print("\n4. Checking individual codes...")
    for code in ['TESTCODE1', 'testcode2', 'NONEXISTENT']:
        is_sent = SentGiftCodesAdapter.is_code_sent(test_guild_id, code)
        status = "✅ Found" if is_sent else "❌ Not found"
        print(f"   {code}: {status}")
    
    # 5. Batch check codes
    print("\n5. Batch checking codes...")
    check_codes = ['TESTCODE1', 'TESTCODE2', 'NEWCODE']
    results = SentGiftCodesAdapter.batch_check_codes(test_guild_id, check_codes)
    for code, sent in results.items():
        status = "✅ Sent" if sent else "❌ Not sent"
        print(f"   {code}: {status}")
    
    # 6. Get statistics
    print("\n6. Getting statistics...")
    stats = SentGiftCodesAdapter.get_stats(test_guild_id)
    print(f"   Total codes: {stats.get('total_codes')}")
    print(f"   Last code: {stats.get('last_code')}")
    print(f"   Sources: {stats.get('sources')}")
    
    # 7. Clean up
    print("\n7. Cleaning up test data...")
    SentGiftCodesAdapter.clear_guild_codes(test_guild_id)
    
    print("\n✅ All basic operations completed successfully!")
    return True


def test_duplicate_prevention():
    """Test that duplicate codes are prevented"""
    print("\n" + "="*60)
    print("Testing Duplicate Prevention")
    print("="*60)
    
    if not mongo_enabled():
        print("⚠️ MongoDB not enabled")
        return False
    
    test_guild_id = 888888888
    test_code = 'DUPLICATETEST'
    
    # Clear existing data
    SentGiftCodesAdapter.clear_guild_codes(test_guild_id)
    
    # Send code first time
    print(f"\n1. Sending code '{test_code}' first time...")
    SentGiftCodesAdapter.mark_codes_sent(test_guild_id, [test_code], 'test1')
    count1 = len(SentGiftCodesAdapter.get_sent_codes(test_guild_id))
    print(f"   Total sent codes: {count1}")
    
    # Try to send same code again
    print(f"\n2. Attempting to send '{test_code}' again (should not duplicate)...")
    SentGiftCodesAdapter.mark_codes_sent(test_guild_id, [test_code], 'test2')
    count2 = len(SentGiftCodesAdapter.get_sent_codes(test_guild_id))
    print(f"   Total sent codes: {count2}")
    
    # Verify no duplication
    if count1 == count2 == 1:
        print("\n✅ Duplicate prevention working correctly!")
        result = True
    else:
        print(f"\n❌ Duplicate prevention failed! Expected 1, got {count2}")
        result = False
    
    # Clean up
    SentGiftCodesAdapter.clear_guild_codes(test_guild_id)
    return result


def test_multi_guild():
    """Test that codes are tracked separately per guild"""
    print("\n" + "="*60)
    print("Testing Multi-Guild Isolation")
    print("="*60)
    
    if not mongo_enabled():
        print("⚠️ MongoDB not enabled")
        return False
    
    guild1 = 111111111
    guild2 = 222222222
    code = 'SHAREDCODE'
    
    # Clear existing data
    SentGiftCodesAdapter.clear_guild_codes(guild1)
    SentGiftCodesAdapter.clear_guild_codes(guild2)
    
    # Send to guild1
    print(f"\n1. Sending '{code}' to guild {guild1}...")
    SentGiftCodesAdapter.mark_codes_sent(guild1, [code], 'test')
    
    # Check guild1 (should have it)
    has_code_g1 = SentGiftCodesAdapter.is_code_sent(guild1, code)
    print(f"   Guild {guild1} has code: {has_code_g1}")
    
    # Check guild2 (should NOT have it)
    has_code_g2 = SentGiftCodesAdapter.is_code_sent(guild2, code)
    print(f"   Guild {guild2} has code: {has_code_g2}")
    
    # Verify isolation
    if has_code_g1 and not has_code_g2:
        print("\n✅ Multi-guild isolation working correctly!")
        result = True
    else:
        print("\n❌ Multi-guild isolation failed!")
        result = False
    
    # Clean up
    SentGiftCodesAdapter.clear_guild_codes(guild1)
    SentGiftCodesAdapter.clear_guild_codes(guild2)
    return result


def test_case_normalization():
    """Test that code normalization works (case-insensitive)"""
    print("\n" + "="*60)
    print("Testing Case Normalization")
    print("="*60)
    
    if not mongo_enabled():
        print("⚠️ MongoDB not enabled")
        return False
    
    test_guild_id = 777777777
    
    # Clear existing data
    SentGiftCodesAdapter.clear_guild_codes(test_guild_id)
    
    # Send code in lowercase
    print("\n1. Sending code 'testcode' (lowercase)...")
    SentGiftCodesAdapter.mark_codes_sent(test_guild_id, ['testcode'], 'test')
    
    # Check with different cases
    print("\n2. Checking code with different cases...")
    test_cases = ['testcode', 'TESTCODE', 'TestCode', 'tEsTcOdE']
    all_found = True
    for code in test_cases:
        is_sent = SentGiftCodesAdapter.is_code_sent(test_guild_id, code)
        print(f"   '{code}': {'✅ Found' if is_sent else '❌ Not found'}")
        if not is_sent:
            all_found = False
    
    if all_found:
        print("\n✅ Case normalization working correctly!")
        result = True
    else:
        print("\n❌ Case normalization failed!")
        result = False
    
    # Clean up
    SentGiftCodesAdapter.clear_guild_codes(test_guild_id)
    return result


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("SentGiftCodesAdapter Test Suite")
    print("="*60)
    
    if not mongo_enabled():
        print("\n❌ MongoDB is not enabled!")
        print("Please set MONGO_URI environment variable.")
        return 1
    
    print(f"\n✅ MongoDB is enabled")
    
    results = []
    
    # Run tests
    results.append(("Basic Operations", test_basic_operations()))
    results.append(("Duplicate Prevention", test_duplicate_prevention()))
    results.append(("Multi-Guild Isolation", test_multi_guild()))
    results.append(("Case Normalization", test_case_normalization()))
    
    # Print summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    print("\n" + "="*60)
    if all_passed:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
