import os

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import chromadb
from chromadb.utils import embedding_functions
from langchain_core.tools import tool

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
db_path = os.path.join(root_dir, "chroma_db")

print("Initializing Catalog Search Tool...")

client = chromadb.PersistentClient(path=db_path)
hf_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = client.get_collection(name="electronics_catalog", embedding_function=hf_ef)

@tool(
    "search_catalog",
    description="Search the electronics catalog and return the top matches.",
)
def search_catalog(query: str) -> str:
    
    print(f"\n[Tool Execution] Agent is searching database for: '{query}'")
    
    results = collection.query(
        query_texts=[query],
        n_results=3 
    )
    
    if not results['documents'][0]:
        return "No products found for this query."
        
    formatted_results = []
    for i in range(len(results['documents'][0])):
        title = results['metadatas'][0][i]['title']
        price = results['metadatas'][0][i]['price']
        categories = results['metadatas'][0][i]['categories']
        
        display_price = "Price unavailable" if str(price).lower() == "nan" else f"${price}"
            
        formatted_results.append(
            f"Product {i+1}:\n"
            f"- Title: {title}\n"
            f"- Price: {display_price}\n"
            f"- Category: {categories}\n"
        )
        
    return "\n".join(formatted_results)