import pymongo
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'gsm_db')

try:
    client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=2000)
    db = client[db_name]
    
    collections = ['editais_gsm', 'editais_normalizados', 'licitacoes', 'editais_sync']
    
    for coll_name in collections:
        coll = db[coll_name]
        count_objeto = coll.count_documents({'objeto': {'$regex': 'canabidiol', '$options': 'i'}})
        total = coll.count_documents({})
        print(f"Collection {coll_name}: {count_objeto} results for canabidiol (Total: {total})")
    
except Exception as e:
    print(f"Error: {e}")
