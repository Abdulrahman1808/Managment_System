from dotenv import load_dotenv
load_dotenv()  # Load environment variables FIRST

import os
from pymongo import MongoClient, errors
from bson import ObjectId
from constants import *
from ui_elements import show_error, show_success
import pandas as pd
import atexit
import json
from datetime import datetime
import tkinter as tk
from tkinter import messagebox
import re
import shutil

# MongoDB Connection Variables
client = None
db = None

def ensure_data_directories():
    """Ensure data directories exist"""
    os.makedirs(EXCEL_DATA_PATH, exist_ok=True)
    os.makedirs(MONGODB_DATA_PATH, exist_ok=True)

def initialize_db():
    """Initialize MongoDB connection"""
    global client, db
    try:
        # Ensure data directories exist
        ensure_data_directories()
        
        # Connect to MongoDB
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DB_NAME]
        
        # Test the connection
        client.server_info()
        print("[DEBUG] Successfully connected to MongoDB")
        
        # Ensure all collections exist
        for collection_name in MONGODB_COLLECTIONS.values():
            ensure_collection(collection_name)
            print(f"[DEBUG] Ensured collection exists: {collection_name}")
        
        return True
    except errors.ConnectionFailure as e:
        print(f"[ERROR] Could not connect to MongoDB: {str(e)}")
        show_error(f"Could not connect to MongoDB: {str(e)}")
        return False
    except Exception as e:
        print(f"[ERROR] Database error: {str(e)}")
        show_error(f"Database error: {str(e)}")
        return False

def ensure_collection(collection_name):
    """Ensure a collection exists in MongoDB"""
    if db is not None and collection_name not in db.list_collection_names():
        db.create_collection(collection_name)

def load_data(data_type):
    """Load data from both MongoDB and JSON file with proper synchronization"""
    if data_type not in MONGODB_COLLECTIONS:
        print(f"[ERROR] Unknown data type: {data_type}")
        return None

    try:
        # Initialize database if not already done
        if db is None:
            initialize_db()

        # Ensure collection exists
        if db is not None:
            ensure_collection(MONGODB_COLLECTIONS[data_type])

        # Try to load from MongoDB first
        if db is not None:
            collection = db[MONGODB_COLLECTIONS[data_type]]
            data = list(collection.find())
            # Convert ObjectId to string for JSON serialization
            for item in data:
                if '_id' in item:
                    item['_id'] = str(item['_id'])
            print(f"[DEBUG] Loaded {len(data)} items from MongoDB")
            
            # Save to JSON file for backup
            filename = os.path.join(MONGODB_DATA_PATH, f"{MONGODB_COLLECTIONS[data_type]}.json")
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"[DEBUG] Saved {len(data)} items to {filename}")
            
            # Export to Excel for consistency
            export_to_excel(data_type)
            
            return data
        else:
            # If MongoDB is not available, try to load from JSON
            filename = os.path.join(MONGODB_DATA_PATH, f"{MONGODB_COLLECTIONS[data_type]}.json")
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
                print(f"[DEBUG] Loaded {len(data)} items from {filename}")
                
                # Export to Excel for consistency
                export_to_excel(data_type)
                
                return data
            else:
                # If JSON doesn't exist, try to load from Excel
                excel_path = EXCEL_FILES[data_type]
                if os.path.exists(excel_path):
                    print(f"[DEBUG] Loading from Excel: {excel_path}")
                    df = pd.read_excel(excel_path)
                    data = df.to_dict('records')
                    
                    # Save to JSON for future use
                    with open(filename, 'w') as f:
                        json.dump(data, f, indent=4)
                    print(f"[DEBUG] Saved {len(data)} items to {filename}")
                    
                    return data
                else:
                    print(f"[DEBUG] No data files found, returning empty list")
                    return []
    except Exception as e:
        print(f"[ERROR] Error loading data: {str(e)}")
        import traceback
        print(f"[TRACEBACK] {traceback.format_exc()}")
        return []

def save_data(data_type, data):
    """Save data to both MongoDB and JSON file"""
    if data_type not in MONGODB_COLLECTIONS:
        print(f"[ERROR] Unknown data type for saving: {data_type}")
        return False

    try:
        # Initialize database if not already done
        if db is None:
            if not initialize_db():
                print("[ERROR] Failed to initialize database")
                return False

        # Ensure collection exists
        if db is not None:
            ensure_collection(MONGODB_COLLECTIONS[data_type])
            print(f"[DEBUG] Ensured collection exists: {MONGODB_COLLECTIONS[data_type]}")

        # Save to JSON file in MongoDB data path
        filename = os.path.join(MONGODB_DATA_PATH, f"{MONGODB_COLLECTIONS[data_type]}.json")
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"[DEBUG] Saved {len(data)} items to {filename}")
        
        # Save to MongoDB if connection is available
        if db is not None:
            collection = db[MONGODB_COLLECTIONS[data_type]]
            # Clear existing data
            collection.delete_many({})
            print(f"[DEBUG] Cleared existing data from {MONGODB_COLLECTIONS[data_type]}")
            
            # Insert new data
            if data:
                # Convert string IDs back to ObjectId for MongoDB
                for item in data:
                    if '_id' in item and isinstance(item['_id'], str):
                        try:
                            item['_id'] = ObjectId(item['_id'])
                        except:
                            # If conversion fails, remove the _id field to let MongoDB generate a new one
                            del item['_id']
                
                # Insert data in batches to avoid memory issues
                batch_size = 100
                for i in range(0, len(data), batch_size):
                    batch = data[i:i + batch_size]
                    collection.insert_many(batch)
                    print(f"[DEBUG] Inserted batch of {len(batch)} items")
                
                print(f"[DEBUG] Saved {len(data)} items to MongoDB {MONGODB_COLLECTIONS[data_type]} collection")
            else:
                print("[DEBUG] No data to save to MongoDB")
        
        # Export to Excel after saving to JSON and MongoDB
        if export_to_excel(data_type):
            print(f"[DEBUG] Successfully exported data to Excel")
        else:
            print(f"[WARNING] Failed to export data to Excel")
        
        return True
    except Exception as e:
        print(f"[ERROR] Error saving data: {str(e)}")
        import traceback
        print(f"[TRACEBACK] {traceback.format_exc()}")
        return False

def export_to_excel(data_type):
    """Export data to Excel file"""
    if data_type not in EXCEL_FILES:
        print(f"[ERROR] Unknown data type for Excel export: {data_type}")
        return False

    try:
        data = load_data(data_type)
        if data is None:
            return False

        df = pd.DataFrame(data)
        excel_path = EXCEL_FILES[data_type]
        df.to_excel(excel_path, index=False)
        print(f"[DEBUG] Exported data to {excel_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Error exporting to Excel: {str(e)}")
        return False

def import_from_excel(data_type):
    """Import data from Excel file and sync with database"""
    if data_type not in EXCEL_FILES:
        print(f"[ERROR] Unknown data type for Excel import: {data_type}")
        return False

    try:
        # Initialize database if not already done
        if db is None:
            if not initialize_db():
                print("[ERROR] Failed to initialize database")
                return False

        excel_path = EXCEL_FILES[data_type]
        required_cols = []
        if data_type == 'products':
            required_cols = ['name', 'type', 'flavor', 'quantity', 'sale_type', 'price', 'status', 'image_path', 'barcode']
        # إذا لم يوجد ملف الإكسيل أنشئه بالأعمدة المطلوبة
        if not os.path.exists(excel_path):
            print(f"[DEBUG] Excel file not found: {excel_path}, creating new one.")
            df = pd.DataFrame(columns=required_cols)
            df.to_excel(excel_path, index=False)
        # اقرأ البيانات
        df = pd.read_excel(excel_path)
        # إذا كان هناك أعمدة ناقصة أضفها
        if data_type == 'products':
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                for col in missing:
                    df[col] = '' if col not in ['quantity', 'price'] else 0
                df.to_excel(excel_path, index=False)
                print(f"[DEBUG] Added missing columns to Excel: {missing}")
        data = df.to_dict('records')
        print(f"[DEBUG] Read {len(data)} records from Excel")
        # Ensure collection exists
        if db is not None:
            ensure_collection(MONGODB_COLLECTIONS[data_type])
            print(f"[DEBUG] Ensured collection exists: {MONGODB_COLLECTIONS[data_type]}")
        # Save to both MongoDB and JSON
        if save_data(data_type, data):
            print(f"[DEBUG] Successfully imported {len(data)} items from Excel")
            return True
        else:
            print(f"[ERROR] Failed to save imported data")
            return False
    except Exception as e:
        print(f"[ERROR] Error importing from Excel: {str(e)}")
        import traceback
        print(f"[TRACEBACK] {traceback.format_exc()}")
        return False

def load_credentials():
    """Load credentials from file"""
    try:
        with open('hookah_credentials.txt', 'r') as f:
            return f.read().strip().split(',')
    except FileNotFoundError:
        return None

def save_credentials(username, password):
    """Save credentials to file"""
    try:
        with open('hookah_credentials.txt', 'w') as f:
            f.write(f"{username},{password}")
        return True
    except Exception as e:
        show_error(f"Error saving credentials: {str(e)}")
        return False

def insert_document(collection_name, document):
    """Insert a single document into a collection"""
    if db is None:
        show_error("Database connection not available")
        return None
    try:
        collection = db[collection_name]
        result = collection.insert_one(document)
        return str(result.inserted_id)
    except Exception as e:
        show_error(f"Error inserting document: {str(e)}")
        return None

def update_document(collection_name, document_id, update_data):
    """Update a document in a collection"""
    if db is None:
        show_error("Database connection not available")
        return False
    try:
        collection = db[collection_name]
        result = collection.update_one(
            {'_id': ObjectId(document_id)},
            {'$set': update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        show_error(f"Error updating document: {str(e)}")
        return False

def delete_document(collection_name, document_id):
    """Delete a document from both MongoDB and JSON file"""
    if db is None:
        show_error("Database connection not available")
        return False
    try:
        # Delete from MongoDB
        collection = db[collection_name]
        result = collection.delete_one({'_id': ObjectId(document_id)})
        
        if result.deleted_count > 0:
            # If deleted from MongoDB, update JSON file
            data = list(collection.find())
            # Convert ObjectId to string for JSON serialization
            for item in data:
                if '_id' in item:
                    item['_id'] = str(item['_id'])
            
            filename = os.path.join(MONGODB_DATA_PATH, f"{collection_name}.json")
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
            
            # Update Excel file
            export_to_excel(collection_name)
            
            return True
        return False
    except Exception as e:
        show_error(f"Error deleting document: {str(e)}")
        return False

def get_document(collection_name, document_id):
    """Get a single document by ID"""
    if db is None:
        show_error("Database connection not available")
        return None
    try:
        collection = db[collection_name]
        document = collection.find_one({'_id': ObjectId(document_id)})
        if document:
            document['_id'] = str(document['_id'])
        return document
    except Exception as e:
        show_error(f"Error getting document: {str(e)}")
        return None

def get_next_id(data_type):
    """Get the next available ID for a data type"""
    if data_type not in MONGODB_COLLECTIONS:
        print(f"[ERROR] Unknown data type for ID generation: {data_type}")
        return None

    try:
        # Initialize database if not already done
        if db is None:
            if not initialize_db():
                print("[ERROR] Failed to initialize database")
                return None

        # Ensure collection exists
        if db is not None:
            ensure_collection(MONGODB_COLLECTIONS[data_type])
            collection = db[MONGODB_COLLECTIONS[data_type]]
            
            # Get all documents
            documents = list(collection.find())
            
            if not documents:
                # If no documents exist, start with ID 1
                return 1
            
            # Get the highest ID
            max_id = 0
            for doc in documents:
                item_id = doc.get('id')
                if item_id is not None:
                    # Convert to string for regex matching
                    item_id_str = str(item_id)
                    # Extract numeric part
                    numeric_part_match = re.match(r'^\d+', item_id_str)
                    if numeric_part_match:
                        numeric_id = int(numeric_part_match.group())
                        max_id = max(max_id, numeric_id)
            
            # Return next ID
            return max_id + 1
            
    except Exception as e:
        print(f"[ERROR] Error generating next ID: {str(e)}")
        import traceback
        print(f"[TRACEBACK] {traceback.format_exc()}")
        return None

def format_date(date):
    """Format date to string"""
    if isinstance(date, datetime):
        return date.strftime('%Y-%m-%d %H:%M:%S')
    return date

def validate_data(data_type, data):
    """Validate data before saving"""
    required_fields = {
        'products': ['name', 'category', 'price', 'quantity', 'status'],
        'inventory': ['name', 'category', 'quantity', 'min_quantity', 'location'],
        'suppliers': ['name', 'contact', 'email', 'phone', 'status'],
        'sales': ['items', 'total', 'date']
    }
    
    if data_type not in required_fields:
        return False
    
    for field in required_fields[data_type]:
        if field not in data:
            return False
    
    return True

def search_data(data_type, query):
    """Search data by query"""
    data = load_data(data_type)
    if not query:
        return data
    
    results = []
    query = query.lower()
    
    for item in data:
        for value in item.values():
            if isinstance(value, str) and query in value.lower():
                results.append(item)
                break
    
    return results

def filter_data(data_type, filters):
    """Filter data by criteria"""
    data = load_data(data_type)
    if not filters:
        return data
    
    results = data
    for key, value in filters.items():
        results = [item for item in results if item.get(key) == value]
    
    return results

def close_connection():
    """Close the MongoDB connection"""
    global client
    if client is not None:
        client.close()

def import_excel_to_db(file_path, collection_name):
    """Import data from Excel file to MongoDB"""
    try:
        # Read Excel file
        df = pd.read_excel(file_path)
        
        # Convert DataFrame to list of dictionaries
        data = df.to_dict('records')
        
        # Insert data into MongoDB
        collection = get_collection(collection_name)
        if collection:
            collection.insert_many(data)
            return True
    except Exception as e:
        print(f"Error importing data: {str(e)}")
        return False

def get_collection(collection_name):
    """Get a MongoDB collection"""
    if db is None:
        show_error("Database connection not available")
        return None
    try:
        return db[collection_name]
    except Exception as e:
        show_error(f"Error getting collection: {str(e)}")
        return None

def load_data(collection_name):
    """Load data from MongoDB collection"""
    try:
        collection = get_collection(collection_name)
        if collection is not None:
            # Get all documents and remove _id field
            documents = list(collection.find({}, {'_id': 0}))
            return documents
    except Exception as e:
        print(f"Error loading data: {str(e)}")
    return []

def delete_document(collection_name, document_id):
    """Delete a document from MongoDB collection"""
    try:
        collection = get_collection(collection_name)
        if collection is not None:
            result = collection.delete_one({'_id': document_id})
            return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting document: {str(e)}")
    return False

# Initialize database connection when module loads
if initialize_db():
    # Initialize collections
    collections = ['products', 'suppliers', 'employees', 'sales']
    for collection in collections:
        ensure_collection(collection)
else:
    show_error("Failed to initialize database connection")

# Close the connection when the program exits
atexit.register(close_connection)
