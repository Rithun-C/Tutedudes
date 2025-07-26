import os
import sqlite3
import re
import google.generativeai as genai
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
SENSITIVE_RE = re.compile(r"(password|email|token|hash)", re.I)

client = PersistentClient(path="chroma_db")
collection = client.get_or_create_collection("ecom_full")

def get_embedding(text: str):
    resp = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="retrieval_document"
    )
    return resp["embedding"]

# Discover all user tables (skip sqlite internal tables)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
tables = [row[0] for row in cursor.fetchall()]
print(f"Found {len(tables)} tables to process…")

total_rows = 0
for table in tables:
    # get columns
    cursor.execute(f"PRAGMA table_info('{table}')")
    cols_info = cursor.fetchall()  # cid, name, type, notnull, dflt, pk
    cols = [c[1] for c in cols_info if not SENSITIVE_RE.search(c[1])]
    if not cols:
        continue
    col_list = ", ".join(cols)
    cursor.execute(f"SELECT rowid, {col_list} FROM {table}")
    rows = cursor.fetchall()
    total_rows += len(rows)
    for row in rows:
        rowid = row[0]
        values = row[1:]
        parts = []
        for col_name, val in zip(cols, values):
            if val is None:
                continue
            parts.append(f"{col_name}: {val}")
        if not parts:
            continue
        doc_text = f"Table: {table}\n" + " | ".join(parts)
        emb = get_embedding(doc_text)
        doc_id = f"{table}:{rowid}"
        try:
            collection.add(documents=[doc_text], embeddings=[emb], ids=[doc_id])
        except Exception:
            # already exists – replace
            collection.update(ids=[doc_id], embeddings=[emb], documents=[doc_text])

print(f"Embedded {total_rows} rows across all tables. Stored in chroma_db/ecom_full")
