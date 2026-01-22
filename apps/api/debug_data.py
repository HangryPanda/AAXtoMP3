import asyncio
import os
import sys
from pprint import pprint

# Add apps/api to python path
sys.path.append(os.path.join(os.getcwd(), "apps", "api"))

from db.session import get_session
from db.models import Book
from sqlalchemy import select

async def debug_book_data():
    async for session in get_session():
        result = await session.execute(select(Book).limit(10))
        books = result.scalars().all()
        
        for book in books:
            print(f"ASIN: {book.asin}")
            print(f"Updated At: {book.updated_at}")
            print(f"Authors JSON (raw): {book.authors_json}")
            print(f"Product Images JSON (raw): {book.product_images_json}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(debug_book_data())
