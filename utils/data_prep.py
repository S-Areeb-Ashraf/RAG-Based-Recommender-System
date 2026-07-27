import gzip
import json
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import os

def clean_data(data_list):
    df = pd.DataFrame(data_list)
    
    cols = ['asin', 'title', 'description', 'price', 'categories']
    for col in cols:
        if col not in df.columns:
            df[col] = ""
            
    df = df[cols].copy()
    df = df.dropna(subset=['title'])
    df = df[df['title'].str.strip() != ""]
    
    df['price'] = df['price'].astype(str)
    
    df['description'] = df['description'].apply(lambda x: " ".join(x) if isinstance(x, list) else str(x))
    df['categories'] = df['categories'].apply(lambda x: " > ".join(x[0]) if isinstance(x, list) and len(x) > 0 else str(x))
    
    df['combined_text'] = df.apply(
        lambda row: f"Product: {row['title']}. Category: {row['categories']}. Description: {row['description']}", 
        axis=1
    )
    return df

def process_in_chunks(file_path: str, output_path: str, chunk_size: int = 50000):
    print(f"Streaming ALL records from {file_path} in chunks of {chunk_size}...")
    
    if os.path.exists(output_path):
        os.remove(output_path)
        
    data_chunk = []
    chunk_counter = 1
    total_processed = 0
    parquet_writer = None

    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
        for line in f:
            data_chunk.append(json.loads(line))
            
            if len(data_chunk) == chunk_size:
                df = clean_data(data_chunk)
                table = pa.Table.from_pandas(df, preserve_index=False) 
                
                if parquet_writer is None:
                    parquet_writer = pq.ParquetWriter(output_path, table.schema)
                    
                parquet_writer.write_table(table)
                
                print(f"Processed chunk {chunk_counter} ({total_processed + len(df)} valid records saved so far)")
                
                total_processed += len(df)
                chunk_counter += 1
                data_chunk = [] 
                
        if len(data_chunk) > 0:
            df = clean_data(data_chunk)
            if not df.empty:
                table = pa.Table.from_pandas(df, preserve_index=False)
                if parquet_writer is None:
                    parquet_writer = pq.ParquetWriter(output_path, table.schema)
                parquet_writer.write_table(table)
                total_processed += len(df)
                print(f"Processed final chunk.")

    if parquet_writer:
        parquet_writer.close()
        
    print(f"\nFile processed. Total valid records saved: {total_processed}")


if __name__ == "__main__":
    INPUT_FILE = "data/meta_Electronics.jsonl.gz"
    OUTPUT_FILE = "data/cleaned_electronics.parquet"
    
    process_in_chunks(INPUT_FILE, OUTPUT_FILE, chunk_size=50000)