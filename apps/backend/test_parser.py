import asyncio
import traceback
from app.services.parser import parse_document

async def run():
    print("Testing parse_document...")
    try:
        with open("test.pdf", "rb") as f:
            content = f.read()
        markdown = await parse_document(content, "test.pdf")
        print("Success, length:", len(markdown))
    except Exception as e:
        print("PARSE ERROR:", type(e), str(e))
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
