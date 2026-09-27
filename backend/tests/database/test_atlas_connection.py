import asyncio
import getpass
import os

import certifi
from dotenv import load_dotenv
from pymongo import AsyncMongoClient


async def main():
    load_dotenv()

    uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("MONGODB_DATABASE")

    if not uri:
        raise RuntimeError("MONGODB_URI is not set")

    if not database_name:
        raise RuntimeError("MONGODB_DATABASE is not set")

    print("Connecting to MongoDB Atlas...")
    password = getpass.getpass("Enter Atlas password: ")

    client = AsyncMongoClient(
        uri,
        username="credence",
        password=password,
        authSource="admin",
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
    )

    try:
        await client.admin.command("ping")

        print()
        print("========================================")
        print("ATLAS CONNECTION: SUCCESS")
        print("========================================")
        print(f"Database: {database_name}")

    except Exception as exc:
        print()
        print("========================================")
        print("ATLAS CONNECTION: FAILED")
        print("========================================")
        print(f"{type(exc).__name__}: {exc}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())