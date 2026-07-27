import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
from tqdm import tqdm
import os

def build_local_db_fast(parquet_path, db_path, limit=5000):
    print(f"Loading {limit} records from {parquet_path}...")
    df = pd.read_parquet(parquet_path).head(limit)
    
    df['asin'] = [f"prod_{i}" for i in range(len(df))]
    
    print(f"Creating Windows-native ChromaDB at {db_path}...")
    client = chromadb.PersistentClient(path=db_path)
    
    hf_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    
    collection = client.get_or_create_collection(
        name="electronics_catalog", 
        embedding_function=hf_ef
    )

    batch_size = 1000
    for i in tqdm(range(0, len(df), batch_size), desc="Building Index"):
        batch = df.iloc[i : i + batch_size]
        collection.add(
            ids=batch['asin'].tolist(),
            documents=batch['combined_text'].tolist(),
            metadatas=batch.apply(lambda r: {
                "title": str(r['title'])[:500],
                "price": str(r['price']),
                "categories": str(r['categories'])
            }, axis=1).tolist()
        )

    print(f"\nSUCCESS! Local database built with {collection.count()} records.")

if __name__ == "__main__":
    build_local_db_fast("data/cleaned_electronics.parquet", "chroma_db")