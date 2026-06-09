import os
from dotenv import load_dotenv
from fastapi import FastAPI, Response, Request
from fastapi.responses import StreamingResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaDocument, DocumentAttributeAudio

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STRING_SESSION = os.getenv("STRING_SESSION")
CHANNEL = os.getenv("CHANNEL")

app = FastAPI()

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

@app.on_event("startup")
async def startup():
    await client.connect()
    print("Telethon connected!")

@app.on_event("shutdown")
async def shutdown():
    await client.disconnect()

@app.get("/")
async def root():
    return {"status": "NoxMusic API running!"}

@app.get("/songs")
async def get_songs():
    songs = []
    try:
        async for message in client.iter_messages(CHANNEL, limit=100):
            if not message.media:
                continue
            if not isinstance(message.media, MessageMediaDocument):
                continue

            doc = message.media.document
            mime = doc.mime_type or ""

            if "audio" not in mime:
                continue

            title = f"Track {message.id}"
            duration = 0

            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeAudio):
                    duration = attr.duration or 0
                    if attr.title:
                        title = attr.title

            songs.append({
                "id": message.id,
                "title": title,
                "duration": duration,
                "size": doc.size,
                "thumb": f"/thumb/{message.id}",
                "stream": f"/stream/{message.id}"
            })

    except Exception as e:
        return {"error": str(e)}

    return songs

@app.get("/thumb/{message_id}")
async def get_thumb(message_id: int):
    try:
        message = await client.get_messages(CHANNEL, ids=message_id)
        if not message or not message.media:
            return Response(status_code=404)

        thumb_bytes = await client.download_media(
            message.media,
            bytes,
            thumb=-1
        )

        if thumb_bytes:
            return Response(
                content=thumb_bytes,
                media_type="image/jpeg"
            )
    except Exception as e:
        print(f"Thumb error: {e}")

    return Response(status_code=404)

@app.get("/stream/{message_id}")
async def stream_audio(message_id: int, request: Request):
    try:
        message = await client.get_messages(CHANNEL, ids=message_id)
        if not message or not message.media:
            return Response(status_code=404)

        doc = message.media.document
        file_size = doc.size

        range_header = request.headers.get("Range")

        if range_header:
            start, end = 0, file_size - 1
            range_val = range_header.replace("bytes=", "")
            parts = range_val.split("-")
            start = int(parts[0])
            if parts[1]:
                end = int(parts[1])

            chunk_size = end - start + 1

            async def generator():
                async for chunk in client.iter_download(
                    message.media,
                    offset=start,
                    limit=chunk_size,
                    chunk_size=512*1024
                ):
                    yield chunk

            return StreamingResponse(
                generator(),
                status_code=206,
                media_type="audio/mpeg",
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(chunk_size),
                }
            )

        async def full_generator():
            async for chunk in client.iter_download(
                message.media,
                chunk_size=512*1024
            ):
                yield chunk

        return StreamingResponse(
            full_generator(),
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            }
        )

    except Exception as e:
        print(f"Stream error: {e}")
        return Response(status_code=500)
