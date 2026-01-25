
import asyncio
import json
import os
import sys
from datetime import datetime
from uuid import UUID

# Add apps/api to path (3 levels up from scripts/developer_tools)
current_dir = os.path.dirname(os.path.abspath(__file__))
api_root = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.append(api_root)

from db.session import get_session
from db.models import Book
from sqlalchemy import select

def json_serializer(obj):
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, (UUID,)):
        return str(obj)
    return str(obj)

async def main():
    # You can change this ASIN or pass it as an argument in the future
    asin = "B0BKR654B3"
    print(f"Fetching book {asin} from DB...")
    
    async for session in get_session():
        stmt = select(Book).where(Book.asin == asin)
        result = await session.execute(stmt)
        book = result.scalar_one_or_none()
        
        if book:
            # Convert SQLAlchemy model to dict
            book_dict = {
                column.name: getattr(book, column.name)
                for column in book.__table__.columns
            }
            
            print("\nSAVED_METADATA_START")
            print(json.dumps(book_dict, default=json_serializer, indent=2))
            print("SAVED_METADATA_END")
        else:
            print(f"Book {asin} not found in DB.")
        break

if __name__ == "__main__":
    asyncio.run(main())
