from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import requests
import shutil
import os
import uuid

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

BOT_TOKEN = "8794090676:AAHS-qb5r5OyNQaFq1xF3uwXh7tOFFqosXs"
GROUP_ID = "-1003932633365"
BOT_USERNAME = "mafia_revolutionclub_bot"
APP_NAME = "app"

class PlayerEntry(BaseModel):
    name: str
    nickname: Optional[str] = ""
    tg_profile: str
    user_id: int

class GameModel(BaseModel):
    id: Optional[int] = None
    title: str
    game_date: str
    game_day: str
    table_type: str
    description: str
    fits: str
    not_fits: str
    time_start: str
    games_count: str
    cost: str
    master: str
    location_name: str
    location_address: str
    location_url: str
    photo_url: Optional[str] = ""
    max_slots: int = 15
    players: List[PlayerEntry] = []
    reserve: List[PlayerEntry] = []
    telegram_message_id: Optional[int] = None

db_games: List[GameModel] = []

@app.post("/upload_photo")
async def upload_photo(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением")
    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    photo_url = f"https://mafia-k0kq.onrender.com/uploads/{filename}"
    return {"photo_url": photo_url}

def sync_with_telegram(game: GameModel):
    try:
        direct_link = f"https://t.me/{BOT_USERNAME}/{APP_NAME}?startapp=game_{game.id}"

        p_list = ""
        for i in range(1, 16):
            if i <= len(game.players):
                p = game.players[i-1]
                # ✅ Показываем ник если он есть
                nick = f" «{p.nickname}»" if p.nickname and p.nickname.strip() else ""
                tg = f" @{p.tg_profile.replace('@','')}" if p.tg_profile != "нет" else ""
                p_list += f"{i}) {p.name}{nick}{tg}\n"
            else:
                p_list += f"{i})\n"

        fits_f = "\n".join([f"{x.strip()} ✅" for x in game.fits.split(',') if x.strip()])
        not_fits_f = "\n".join([f"{x.strip()} ❌" for x in game.not_fits.split(',') if x.strip()])

        text = (
            f"📅 *{game.game_date}, {game.table_type}*\n\n"
            f"*{game.title}*\n\n"
            f"{game.description}\n\n"
            f"*{game.title}*\n"
            f"Подходит:\n{fits_f}\n\n"
            f"Не подходит:\n{not_fits_f}\n\n"
            f"*{game.game_date.upper()}, {game.game_day}*\n"
            f"*{game.time_start}*\n"
            f"*{game.games_count}*\n"
            f"*{game.cost}*\n\n"
            f"Ведущий: {game.master}\n\n"
            f"*Локация*\n"
            f"{game.location_name}\n{game.location_address}\n"
            f"{game.location_url}\n\n"
            f"*Участники:*\n"
            f"{p_list}"
            f"\n👉 [ЗАПИСЬ]({direct_link})"
        )

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/"

        if game.photo_url and not game.telegram_message_id:
            print(f"[TG] Скачиваем фото: {game.photo_url}")
            photo_response = requests.get(game.photo_url, timeout=15)
            print(f"[TG] Фото скачано, размер: {len(photo_response.content)} байт")
            files = {"photo": ("photo.jpg", photo_response.content, "image/jpeg")}
            data  = {"chat_id": GROUP_ID, "caption": text, "parse_mode": "Markdown"}
            res   = requests.post(url + "sendPhoto", data=data, files=files)

        elif game.photo_url and game.telegram_message_id:
            payload = {
                "chat_id": GROUP_ID,
                "message_id": game.telegram_message_id,
                "caption": text,
                "parse_mode": "Markdown"
            }
            res = requests.post(url + "editMessageCaption", json=payload)

        else:
            payload = {
                "chat_id": GROUP_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }
            if game.telegram_message_id:
                payload["message_id"] = game.telegram_message_id
                method = "editMessageText"
            else:
                method = "sendMessage"
            res = requests.post(url + method, json=payload)

        print(f"[TG] Статус ответа: {res.status_code}")
        print(f"[TG] Ответ Telegram: {res.text}")

        res_json = res.json()
        if res_json.get("ok") and not game.telegram_message_id:
            game.telegram_message_id = res_json["result"]["message_id"]
            print(f"[TG] message_id сохранён: {game.telegram_message_id}")
        elif not res_json.get("ok"):
            print(f"[TG] ОШИБКА от Telegram: {res_json.get('description')}")

    except Exception as e:
        print(f"[TG] ИСКЛЮЧЕНИЕ: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

@app.get("/games")
async def get_games(): return db_games

@app.post("/add_game")
async def add_game(game: GameModel):
    game.id = len(db_games) + 1
    db_games.append(game)
    sync_with_telegram(game)
    return {"status": "ok"}

@app.post("/register/{game_id}")
async def register(game_id: int, p: PlayerEntry):
    for g in db_games:
        if g.id == game_id:
            if any(x.user_id == p.user_id for x in g.players + g.reserve):
                return {"status": "exists"}
            if len(g.players) < g.max_slots:
                g.players.append(p)
            else:
                g.reserve.append(p)
            sync_with_telegram(g)
            return {"status": "ok"}
    return {"status": "error"}

@app.post("/cancel/{game_id}")
async def cancel(game_id: int, user_id: int):
    for g in db_games:
        if g.id == game_id:
            g.players = [p for p in g.players if p.user_id != user_id]
            g.reserve = [p for p in g.reserve if p.user_id != user_id]
            if len(g.players) < g.max_slots and g.reserve:
                g.players.append(g.reserve.pop(0))
            sync_with_telegram(g)
            return {"status": "ok"}
    return {"status": "error"}

@app.delete("/delete_game/{game_id}")
async def delete_game(game_id: int):
    global db_games
    db_games = [g for g in db_games if g.id != game_id]
    return {"status": "deleted"}
