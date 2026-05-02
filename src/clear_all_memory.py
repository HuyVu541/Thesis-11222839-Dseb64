import asyncio
import os
import shutil
import sys
from pathlib import Path

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings

async def clear_postgres():
    """Clear all data from Postgres checkpointer tables."""
    print("Clearing Postgres tables...")
    try:
        from psycopg import AsyncConnection
        async with await AsyncConnection.connect(settings.database_url, autocommit=True) as conn:
            async with conn.cursor() as cur:
                # Truncate tables
                tables = [
                    "checkpoints", "checkpoint_blobs", "checkpoint_writes",
                    "sessions",    # Clear session list
                ]
                for table in tables:
                    try:
                        await cur.execute(f"TRUNCATE TABLE {table} CASCADE")
                        print(f"✓ Truncated {table}")
                    except Exception as e:
                        print(f"⚠ Could not truncate {table}: {e}")
                
    except Exception as e:
        print(f"❌ Error clearing Postgres: {e}")

def clear_filesystem():
    """Clear memory directory (except index/ config files)."""
    print("\nClearing Filesystem Memory...")
    base_path = Path("memory")
    
    if not base_path.exists():
        print("Memory directory does not exist.")
        return

    dirs_to_clear = [
        "rag_storage", "rag_baseline", "schema",
        "metrics", "queries", "insights", "sessions",
    ]
    
    for d in dirs_to_clear:
        dir_path = base_path / d
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"✓ Deleted memory/{d}/")
        # Re-create empty directory immediately
        dir_path.mkdir(parents=True, exist_ok=True)
        
    # Delete the global edge graph
    graph_file = base_path / "_graph.json"
    if graph_file.exists():
        graph_file.unlink()
        print("✓ Deleted memory/_graph.json")

def clear_faiss():
    """Reset FAISS index."""
    print("\nClearing FAISS Index...")
    # Clear both possible FAISS locations
    for path_str in ["memory/index", "memory/rag_baseline/faiss_index"]:
        index_path = Path(path_str)
        if index_path.exists():
            shutil.rmtree(index_path)
            print(f"✓ Deleted {path_str}/")
    
    # Re-create empty dirs
    Path("memory/index").mkdir(parents=True, exist_ok=True)
    print("✓ Re-created empty index directories")
    
    # Note: The backend will re-initialize a fresh index on next startup

async def main():
    print("!!! DANGER: THIS WILL DELETE ALL AI MEMORY !!!")
    print("This includes:")
    print("1. All chat history (Postgres)")
    print("2. All stored artifacts (Filesystem)")
    print("3. All vector embeddings (FAISS)")
    
    confirm = input("Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("Operation cancelled.")
        return

    await clear_postgres()
    clear_filesystem()
    clear_faiss()
    
    print("\n\nAll memory cleared successfully. Please restart the backend.")

if __name__ == "__main__":
    asyncio.run(main())
