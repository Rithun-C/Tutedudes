"""Embed product data into Chroma vector DB.
Run:  python embed_data.py
Ensure OPENAI_API_KEY env var is set.
"""
import os
import sqlite3
import google.generativeai as genai
import chromadb
from chromadb import PersistentClient

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


DB_PATH = os.path.join("ecom", "db.sqlite3") if os.path.exists("ecom/db.sqlite3") else "db.sqlite3"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
# Fetch product info along with category name and vendor username (no emails/passwords)
cursor.execute(
    """
    SELECT p.id, p.name, p.description, COALESCE(c.name, ''), u.username
    FROM ecomApp_product p
    LEFT JOIN ecomApp_category c ON p.category_id = c.id
    LEFT JOIN ecomApp_customuser u ON p.vendor_id = u.id
    """
)
rows = cursor.fetchall()

client = PersistentClient(path="chroma_db")
collection = client.get_or_create_collection("product_data")

print(f"Embedding {len(rows)} products…")

def get_embedding(text: str):
    resp = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="retrieval_document"
    )
    return resp["embedding"]

for pid, name, desc, category, vendor_username in rows:
    doc_text = f"Product: {name}\nCategory: {category}\nVendor: {vendor_username}\nDescription: {desc}"
    emb = get_embedding(doc_text)
    collection.add(
        documents=[doc_text],
        embeddings=[emb],
        ids=[str(pid)],
        metadatas=[{"name": name, "category": category, "vendor": vendor_username}]
    )

print("Embedding completed and stored in chroma_db/")
