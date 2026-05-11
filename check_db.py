import pymongo
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'gsm_db')

try:
    client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=2000)
    db = client[db_name]
    
    count_objeto = db.editais_gsm.count_documents({'objeto': {'$regex': 'canabidiol', '$options': 'i'}})
    count_items = db.editais_gsm.count_documents({'itens_clonados.descricao': {'$regex': 'canabidiol', '$options': 'i'}})
    
    print(f"Canabidiol in objeto: {count_objeto}")
    print(f"Canabidiol in items: {count_items}")
    
    # Check total documents
    total = db.editais_gsm.count_documents({})
    print(f"Total documents in editais_gsm: {total}")
    
except Exception as e:
    print(f"Error: {e}")
