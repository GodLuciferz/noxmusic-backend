import os
from dotenv import load_dotenv
from fastapi import FastAPI, Response, Request
from fastapi.responses import StreamingResponse
from pyrogram import Client

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STRING_SESSION = os.getenv("STRING_SESSION")
CHANNEL = os.getenv("CHANNEL")

app = FastAPI()

bot = Client(
    name="noxmusic",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION
)

channel_id = None

@app.on_event("startup")
async def startup():
    global channel_id
    await bot.start()
    try:
        chat = await bot.get_chat(CHANNEL)
        channel_id = chat.id
        print(f"Channel found: {chat.title} | ID: {channel_id}")
    except Exception as e:
        print(f"Channel resolve error: {e}")
    print("Pyrogram connected!")

@app.on_event("shutdown")
async def shutdown():
    await bot.stop()

@app.get("/")
async def root():
    return {"status": "NoxMusic API running!", "channel": str(channel_id)}

@app.get("/songs")
async def get_songs():
    songs = []
    try:
        async for message in bot.get_chat_history(channel_id, limit=100):
            if not message.audio:
                continue
            audio = message.audio
            songs.append({
                "id": message.id,
                "title": audio.title or audio.file_name or f"Track {message.id}",
                "duration": audio.duration or 0,
                "size": audio.file_size or 0,
                "thumb": f"/thumb/{message.id}",
                "stream": f"/stream/{message.id}"
            })
    except Exception as e:
        return {"error": str(e)}
    return songs

@app.get("/thumb/{message_id}")
async def get_thumb(message_id: int):
    try:
        message = await bot.get_messages(channel_id, message_id)
        if not message or not message.audio:
            return Response(status_code=404)
        if not message.audio.thumbs:
            return Response(status_code=404)
        thumb_bytes = await bot.download_media(
            message.audio.thumbs[0].file_id,
            in_memory=True
        )
        if thumb_bytes:
            thumb_bytes.seek(0)
            return Response(
                content=thumb_bytes.read(),
                media_type="image/jpeg"
            )
    except Exception as e:
        print(f"Thumb error: {e}")
    return Response(status_code=404)

@app.get("/stream/{message_id}")
async def stream_audio(message_id: int, request: Request):
    try:
        message = await bot.get_messages(channel_id, message_id)
        if not message or not message.audio:
            return Response(status_code=404)

        file_size = message.audio.file_size
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
                async for chunk in bot.stream_media(
                    message.audio,
                    offset=start // (1024 * 1024),
                    limit=chunk_size
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
            async for chunk in bot.stream_media(message.audio):
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
