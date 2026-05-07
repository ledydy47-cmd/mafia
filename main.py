from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import requests

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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
    date_time: str
    table_type: str = "Вайбовый стол" # Тип стола
    description: str = ""
    fits: str = "" # Подходит для
    not_fits: str = "" # Не подходит для
    master: str = ""
    location: str = ""
    location_url: str = ""
    cost: str = ""
    duration: str = ""
    max_slots: int = 15
    photo_url: Optional[str] = ""
    players: List[PlayerEntry] = []
    reserve: List[PlayerEntry] = []
    telegram_message_id: Optional[int] = None

db_games: List[GameModel] = []

def sync_with_telegram(game: GameModel):
    try:
        direct_link = f"https://t.me/{BOT_USERNAME}/{APP_NAME}?startapp=game_{game.id}"
        
        # Нумерованный список 1-15
        players_list = ""
        for i in range(1, 16):
            if i <= len(game.players):
                p = game.players[i-1]
                players_list += f"{i}) {p.name} {p.nickname} @{p.tg_profile.replace('@','')}\n"
            else:
                players_list += f"{i})\n"

        # Формирование списков с эмодзи
        fits_list = "\n".join([f"{item.strip()} ✅" for item in game.fits.split(',') if item.strip()])
        not_fits_list = "\n".join([f"{item.strip()} ❌" for item in game.not_fits.split(',') if item.strip()])

        text = (
            f"🖼 *{game.date_time}, {game.table_type}*\n\n"
            f"*{game.title}*\n\n"
            f"{game.description}\n\n"
            f"*Подходит:*\n{fits_list}\n\n"
            f"*Не подходит:*\n{not_fits_list}\n\n"
            f"📅 {game.date_time.upper()}\n"
            f"⏰ {game.duration}\n"
            f"💰 {game.cost}\n\n"
            f"🎙 Ведущий: {game.master}\n\n"
            f"📍 *Локация*\n"
            f"{game.location}\n"
            f"{game.location_url}\n\n"
            f"*Участники:*\n"
            f"{players_list}"
            f"\n👉 [ЗАПИСЬ]({direct_link})"
        )

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/"
        method = "sendPhoto" if game.photo_url else "sendMessage"
        
        payload = {
            "chat_id": GROUP_ID,
            "parse_mode": "Markdown",
        }

        if game.photo_url:
            payload["photo"] = game.photo_url
            payload["caption"] = text
        else:
            payload["text"] = text

        if not game.telegram_message_id:
            res = requests.post(url + method, json=payload).json()
            if res.get("ok"):
                game.telegram_message_id = res["result"]["message_id"]
        else:
            # Редактирование
            edit_method = "editMessageCaption" if game.photo_url else "editMessageText"
            payload["message_id"] = game.telegram_message_id
            requests.post(url + edit_method, json=payload)

    except Exception as e:
        print(f"Error: {e}")

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
            if len(g.players) < g.max_slots: g.players.append(p)
            else: g.reserve.append(p)
            sync_with_telegram(g)
            return {"status": "ok"}
    return {"status": "error"}

@app.post("/cancel/{game_id}")
async def cancel(game_id: int, user_id: int):
    for g in db_games:
        if g.id == game_id:
            g.players = [p for p in g.players if p.user_id != user_id]
            g.reserve = [p for p in g.reserve if p.user_id != user_id]
            if len(g.players) < g.max_slots and g.reserve: g.players.append(g.reserve.pop(0))
            sync_with_telegram(g)
            return {"status": "ok"}
    return {"status": "error"}

@app.delete("/delete_game/{game_id}")
async def delete_game(game_id: int):
    global db_games
    db_games = [g for g in db_games if g.id != game_id]
    return {"status": "deleted"}
