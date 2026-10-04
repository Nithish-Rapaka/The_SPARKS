import os
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import DESCENDING, MongoClient


class MongoHistoryConfigurationError(RuntimeError):
    pass


def _posts_collection():
    mongo_url = os.getenv("MONGODB_URI")
    if not mongo_url:
        raise MongoHistoryConfigurationError(
            "MONGODB_URI must contain a MongoDB connection URL."
        )

    client = MongoClient(
        mongo_url,
        serverSelectionTimeoutMS=10000,
        tz_aware=True,
    )
    database_name = os.getenv("MONGODB_DATABASE")
    database = (
        client[database_name]
        if database_name
        else client.get_default_database("linkedin_automation")
    )
    return client, database["linkedin_posts"]


def save_linkedin_post(*, prompt, text, image_url):
    client, collection = _posts_collection()
    document = {
        "prompt": prompt,
        "text": text,
        "image_url": image_url,
        "published_at": datetime.now(timezone.utc),
    }

    try:
        result = collection.insert_one(document)
        document["id"] = str(result.inserted_id)
        document["published_at"] = document["published_at"].isoformat()
        return document
    finally:
        client.close()


def get_linkedin_posts():
    client, collection = _posts_collection()
    try:
        documents = collection.find(
            {},
            {
                "prompt": 1,
                "text": 1,
                "image_url": 1,
                "published_at": 1,
            },
        ).sort(
            [("published_at", DESCENDING), ("_id", DESCENDING)]
        ).limit(50)

        return [
            {
                "id": str(document["_id"]),
                "prompt": document["prompt"],
                "text": document["text"],
                "image_url": document["image_url"],
                "published_at": document["published_at"].isoformat(),
            }
            for document in documents
        ]
    finally:
        client.close()


def delete_linkedin_posts(post_ids=None):
    client, collection = _posts_collection()
    try:
        selector = (
            {"_id": {"$in": [ObjectId(post_id) for post_id in post_ids]}}
            if post_ids is not None
            else {}
        )
        result = collection.delete_many(selector)
        return result.deleted_count
    finally:
        client.close()
