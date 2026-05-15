"""
MongoDB Connection Test Script
Run this after adding MONGO_URI to your .env file to verify the connection works.
"""

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient

def test_mongodb_connection():
    """Test MongoDB connection and display database info"""
    
    # Load environment variables
    load_dotenv()
    
    mongo_uri = os.getenv('MONGO_URI')
    db_name = os.getenv('MONGO_DB_NAME', 'discord_bot')
    
    if not mongo_uri:
        print("❌ MONGO_URI not found in .env file")
        print("\nPlease add the following lines to your .env file:")
        print("MONGO_URI=mongodb+srv://yourbook444362_db_user:3KAXZB6hkJ1DAWPT@wosbot.yal4g3b.mongodb.net/?appName=WOSBOT")
        print("MONGO_DB_NAME=discord_bot")
        return False
    
    print("🔍 Testing MongoDB connection...")
    print(f"📍 Database: {db_name}")
    
    try:
        # Create MongoDB client with timeout
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        print("✅ MongoDB connection successful!")
        
        # Get database
        db = client[db_name]
        
        # List collections
        collections = db.list_collection_names()
        print(f"\n📊 Database Info:")
        print(f"   - Database Name: {db.name}")
        print(f"   - Total Collections: {len(collections)}")
        
        if collections:
            print(f"\n📁 Existing Collections:")
            for coll in sorted(collections):
                count = db[coll].count_documents({})
                print(f"   - {coll}: {count} documents")
        else:
            print("\n📁 No collections yet (will be created when data is stored)")
        
        # Test write access
        print("\n🔧 Testing write access...")
        test_collection = db['_connection_test']
        test_collection.insert_one({'test': 'connection', 'timestamp': 'test'})
        test_collection.delete_one({'test': 'connection'})
        print("✅ Write access confirmed!")
        
        print("\n" + "="*60)
        print("✅ MongoDB is configured correctly!")
        print("="*60)
        print("\nYour bot will now use MongoDB as the primary database.")
        print("SQLite will only be used as a fallback if MongoDB is unavailable.")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"\n❌ MongoDB connection failed!")
        print(f"Error: {e}")
        print("\nPlease check:")
        print("1. Your internet connection")
        print("2. MongoDB Atlas cluster is running")
        print("3. IP address is whitelisted (or 0.0.0.0/0 for all IPs)")
        print("4. Username and password are correct")
        return False

if __name__ == "__main__":
    success = test_mongodb_connection()
    sys.exit(0 if success else 1)
