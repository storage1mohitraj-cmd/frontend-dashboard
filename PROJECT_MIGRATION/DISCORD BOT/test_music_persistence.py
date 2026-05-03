"""
Test script to verify music state persistence
Run this after playing some music and before restarting the bot
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_music_persistence():
    """Test if music state is being saved correctly"""
    try:
        from music_state_storage import music_state_storage
        
        print("="*70)
        print("🔍 Testing Music State Persistence")
        print("="*70)
        
        # Initialize storage
        await music_state_storage.initialize()
        
        # Get all saved states
        states = await music_state_storage.get_all_states()
        
        if not states:
            print("\n⚠️  No saved music states found!")
            print("Make sure you:")
            print("  1. Start the bot")
            print("  2. Play some music")
            print("  3. Wait at least 10 seconds (for auto-save)")
            print("  4. Then run this test")
            return
        
        print(f"\n✅ Found {len(states)} saved music state(s)")
        print("="*70)
        
        for idx, state in enumerate(states, 1):
            print(f"\n📊 State #{idx}")
            print(f"  Guild ID: {state.get('guild_id')}")
            print(f"  Voice Channel ID: {state.get('channel_id')}")
            print(f"  Text Channel ID: {state.get('text_channel_id')}")
            
            current = state.get('current_track')
            if current:
                print(f"\n  🎵 Current Track:")
                print(f"    Title: {current.get('title', 'Unknown')}")
                print(f"    Author: {current.get('author', 'Unknown')}")
                print(f"    Position: {current.get('position', 0)}ms ({current.get('position', 0) // 1000}s)")
                print(f"    URI: {current.get('uri', 'N/A')[:50]}...")
            else:
                print(f"\n  🎵 No current track (queue only)")
            
            queue = state.get('queue', [])
            print(f"\n  📝 Queue: {len(queue)} track(s)")
            if queue:
                for i, track in enumerate(queue[:3], 1):  # Show first 3
                    print(f"    {i}. {track.get('title', 'Unknown')} - {track.get('author', 'Unknown')}")
                if len(queue) > 3:
                    print(f"    ... and {len(queue) - 3} more")
            
            print(f"\n  ⚙️  Settings:")
            print(f"    Volume: {state.get('volume', 100)}%")
            print(f"    Loop Mode: {state.get('loop_mode', 'off')}")
            if state.get('playlist_name'):
                print(f"    Playlist: {state.get('playlist_name')}")
            
            print(f"\n  📅 Last Updated: {state.get('updated_at', 'Unknown')}")
        
        print("\n" + "="*70)
        print("✅ Persistence test complete!")
        print("\nNext step: Restart the bot and check if it restores these states")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Error testing persistence: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_music_persistence())
