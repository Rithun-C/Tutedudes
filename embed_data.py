import os
import sqlite3
import google.generativeai as genai
from chromadb import PersistentClient

# --- Configuration ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
DB_PATH = os.path.join("ecom", "db.sqlite3") if os.path.exists("ecom/db.sqlite3") else "db.sqlite3"
CHROMA_PATH = "chroma_db"
# Use a new collection to avoid mixing old and new data structures
COLLECTION_NAME = "product_profiles"

# --- ChromaDB Client ---
client = PersistentClient(path=CHROMA_PATH)
# Delete old collection if it exists, to ensure a fresh start
try:
    client.delete_collection(name=COLLECTION_NAME)
    print(f"Deleted existing collection: '{COLLECTION_NAME}'")
except Exception:
    pass # Collection didn't exist, which is fine

collection = client.create_collection(name=COLLECTION_NAME)
print(f"Recreated collection: '{COLLECTION_NAME}'")

# --- Embedding Function ---
def get_embedding(text: str):
    """Generates an embedding for the given text using the Google AI API."""
    try:
        resp = genai.embed_content(
            model="models/embedding-001",
            content=text,
            task_type="retrieval_document"
        )
        return resp["embedding"]
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

# --- Main Data Processing Logic ---
def main():
    """Fetches product data, combines it with related info, and embeds it."""
    conn = sqlite3.connect(DB_PATH)
    # Use Row factory to access columns by name for better readability
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Fetch all available products with their vendor and category.
    cursor.execute(
        """
        SELECT
            p.id, p.name, p.description, p.price, p.quantity,
            c.name as category_name,
            u.username as vendor_username
        FROM ecomApp_product p
        LEFT JOIN ecomApp_category c ON p.category_id = c.id
        LEFT JOIN ecomApp_customuser u ON p.vendor_id = u.id
        WHERE p.available = 1 AND p.quantity > 0
        """
    )
    products = cursor.fetchall()
    print(f"Found {len(products)} products to process...")

    # 2. For each product, build a comprehensive text document.
    for product in products:
        # Fetch average rating and all feedback comments for this product.
        cursor.execute(
            """
            SELECT
                AVG(rating) as avg_rating,
                GROUP_CONCAT(comment, '; ') as all_comments
            FROM ecomApp_feedback
            WHERE product_id = ?
            """,
            (product['id'],)
        )
        feedback_data = cursor.fetchone()

        # 3. Construct the document text, excluding internal IDs.
        doc_parts = [
            f"Product Name: {product['name']}",
            f"Description: {product['description']}",
            f"Sold by Vendor: {product['vendor_username']}",
            f"Category: {product['category_name'] or 'N/A'}",
            f"Price: Rs. {product['price']:.2f}",
            f"Available Stock: {product['quantity']}"
        ]

        avg_rating_text = "Not yet rated"
        if feedback_data and feedback_data['avg_rating']:
            avg_rating = round(feedback_data['avg_rating'], 1)
            avg_rating_text = f"{avg_rating} out of 5 stars"
        doc_parts.append(f"Average Rating: {avg_rating_text}")

        feedback_text = "No reviews yet"
        if feedback_data and feedback_data['all_comments']:
            feedback_text = feedback_data['all_comments']
        doc_parts.append(f"Customer Feedback Summary: {feedback_text}")

        doc_text = "\n".join(doc_parts)
        doc_id = f"product_profile_{product['id']}"

        # 4. Generate embedding and add to ChromaDB.
        embedding = get_embedding(doc_text)
        if embedding:
            try:
                collection.add(documents=[doc_text], embeddings=[embedding], ids=[doc_id])
            except Exception as e:
                print(f"Error adding document {doc_id} to ChromaDB: {e}")

    conn.close()
    print(f"\nEmbedding process complete. {collection.count()} product profiles stored in '{COLLECTION_NAME}'.")

if __name__ == "__main__":
    main()
