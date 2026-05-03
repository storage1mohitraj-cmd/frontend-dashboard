""""
Test Script for Voice Conversation Feature
Tests the voice conversation system locally
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_audio_processor():
    """Test the audio processor functionality"""
    print("=" * 60)
    print("TESTING AUDIO PROCESSOR")
    print("=" * 60)
    
    try:
        from audio_processor import audio_processor
        print("✅ Audio processor imported successfully")
        
        # Test Whisper model loading
        print("\n📥 Loading Whisper model...")
        model = await audio_processor.load_whisper_model()
        print(f"✅ Whisper model loaded: {audio_processor.model_size}")
        
        # Test TTS generation
        print("\n🔊 Testing text-to-speech generation...")
        test_text = "Hello! This is a test of the voice conversation system."
        audio_bytes = await audio_processor.text_to_speech(test_text, language="en")
        
        if audio_bytes:
            print(f"✅ TTS generated {len(audio_bytes)} bytes of audio")
            
            # Save test audio
            test_path = await audio_processor.save_temp_audio(audio_bytes, format="mp3")
            if test_path:
                print(f"✅ Test audio saved to: {test_path}")
                print("   You can play this file to verify TTS works")
        else:
            print("❌ TTS generation failed")
        
        # Test cleanup
        audio_processor.cleanup_temp_files()
        print("✅ Cleanup successful")
        
        print("\n" + "=" * 60)
        print("AUDIO PROCESSOR TEST PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ AUDIO PROCESSOR TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_voice_cog_import():
    """Test importing the voice conversation cog"""
    print("\n" + "=" * 60)
    print("TESTING VOICE CONVERSATION COG")
    print("=" *60)
    
    try:
        from cogs.voice_conversation import VoiceConversation, VoiceSession
        print("✅ Voice conversation cog imported successfully")
        
        print("✅ VoiceSession class available")
        print("✅ VoiceConversation class available")
        
        print("\n" + "=" * 60)
        print("VOICE COG IMPORT TEST PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ VOICE COG IMPORT TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_dependencies():
    """Test that all required dependencies are installed"""
    print("\n" + "=" * 60)
    print("TESTING DEPENDENCIES")
    print("=" * 60)
    
    dependencies = [
        ("whisper", "OpenAI Whisper"),
        ("gtts", "Google Text-to-Speech"),
        ("speech_recognition", "SpeechRecognition"),
        ("pydub", "PyDub"),
        ("soundfile", "SoundFile"),
    ]
    
    all_ok = True
    for module_name, display_name in dependencies:
        try:
            __import__(module_name)
            print(f"✅ {display_name} ({module_name}) is installed")
        except ImportError:
            print(f"❌ {display_name} ({module_name}) is NOT installed")
            all_ok = False
    
    # Test ffmpeg availability
    import subprocess
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        if result.returncode == 0:
            print("✅ FFmpeg is installed and accessible")
        else:
            print("❌ FFmpeg is installed but not working properly")
            all_ok = False
    except FileNotFoundError:
        print("❌ FFmpeg is NOT installed (required for audio playback)")
        print("   Install with: apt-get install ffmpeg (Linux) or brew install ffmpeg (Mac)")
        all_ok = False
    except Exception as e:
        print(f"⚠️ Could not verify FFmpeg: {e}")
    
    print("\n" + "=" * 60)
    if all_ok:
        print("ALL DEPENDENCIES TEST PASSED")
    else:
        print("SOME DEPENDENCIES ARE MISSING")
        print("Run: pip install -r requirements.txt")
    print("=" * 60)
    return all_ok


async def main():
    """Run all tests"""
    print("\n🎙️ VOICE CONVERSATION FEATURE TEST SUITE")
    print("=" * 60)
    
    # Test dependencies first
    deps_ok = await test_dependencies()
    
    if not deps_ok:
        print("\n⚠️ Some dependencies are missing. Install them first:")
        print("   pip install -r requirements.txt")
        print("\nContinuing with available tests...\n")
    
    # Test cog import
    cog_ok = await test_voice_cog_import()
    
    # Test audio processor
    if deps_ok:
        audio_ok = await test_audio_processor()
    else:
        print("\n⚠️ Skipping audio processor test (dependencies missing)")
        audio_ok = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Dependencies: {'✅ PASS' if deps_ok else '❌ FAIL'}")
    print(f"Voice Cog Import: {'✅ PASS' if cog_ok else '❌ FAIL'}")
    print(f"Audio Processor: {'✅ PASS' if audio_ok else '⚠️ SKIPPED' if not deps_ok else '❌ FAIL'}")
    
    all_passed = deps_ok and cog_ok and audio_ok
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Voice conversation feature is ready to use")
        print("\nNext steps:")
        print("1. Start the bot")
        print("2. Join a voice channel")
        print("3. Use /voice_chat to start a voice conversation")
    else:
        print("\n⚠️ SOME TESTS FAILED")
        print("Please fix the issues above before using voice conversation")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
