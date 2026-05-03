"""
Test MongoDB connection
"""
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
print(f"MONGO_URI from .env: {MONGO_URI[:50]}..." if MONGO_URI else "❌ No MONGO_URI in .env")

# Try reading from mongo_uri.txt
try:
    with open('mongo_uri.txt', 'r') as f:
        mongo_uri_file = f.read().strip()
    print(f"MONGO_URI from file: {mongo_uri_file[:50]}...")
except Exception as e:
    print(f"❌ Error reading mongo_uri.txt: {e}")

# Test connection
if MONGO_URI:
    try:
        from pymongo import MongoClient
        from pymongo.server_api import ServerApi
        
        print("\n🔄 Testing MongoDB connection...")
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'), serverSelectionTimeoutMS=5000)
        
        # Test the connection
        client.admin.command('ping')
        print("✅ MongoDB connection successful!")
        
        # List databases
        dbs = client.list_database_names()
        print(f"📊 Available databases: {dbs}")
        
        client.close()
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
else:
    print("❌ No MONGO_URI configured")
