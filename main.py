import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument
import re

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
CHANNEL = os.getenv("CHANNEL")

app = FastAPI()
client = TelegramClient("session/noxmusic", API_ID, API_HASH)

@app.on_event("startup")
async def startup():
    await client.start()

@app.get("/songs")
async def get_songs():
    songs = []
    async for message in client.iter_messages(CHANNEL, limit=50):
        if message.media and isinstance(message.media, MessageMediaDocument):
            doc = message.media.document
            is_audio = any(
                hasattr(attr, 'title') for attr in doc.attributes
            )
            if is_audio:
                title = "Unknown"
                duration = 0
                for attr in doc.attributes:
                    if hasattr(attr, 'title') and attr.title:
                        title = attr.title
                    if hasattr(attr, 'duration'):
                        duration = attr.duration

                songs.append({
                    "id": message.id,
                    "title": title,
                    "duration": duration,
                    "thumb": f"/thumb/{message.id}",
                    "stream": f"/stream/{message.id}"
                })
    return songs

@app.get("/thumb/{message_id}")
async def get_thumb(message_id: int):
    message = await client.get_messages(CHANNEL, ids=message_id)
    if not message or not message.media:
        return Response(status_code=404)
    
    thumb_bytes = await client.download_media(
        message.media, 
        bytes,
        thumb=-1
    )
    
    if thumb_bytes:
        return Response(content=thumb_bytes, media_type="image/jpeg")
    return Response(status_code=404)

@app.get("/stream/{message_id}")
async def stream_audio(message_id: int):
    message = await client.get_messages(CHANNEL, ids=message_id)
    if not message or not message.media:
        return Response(status_code=404)

    async def generator():
        async for chunk in client.iter_download(message.media):
            yield chunk

    return StreamingResponse(
        generator(),
        media_type="audio/mpeg"
    )
