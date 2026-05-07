from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ВАШИ НАСТРОЙКИ ---
BOT_TOKEN = "8794090676:AAHS-qb5r5OyNQaFq1xF3uwXh7tOFFqosXs" # Пример, вставьте свой актуальный
GROUP_ID = "-1003932633365"
BOT_USERNAME = "mafia_revolutionclub_bot" # Пример
APP_NAME = "app" # Пример

class PlayerEntry(BaseModel):
    name: str
    nickname: Optional[str] = ""
    tg_profile: str
    user_id: int

class GameModel(BaseModel):
    id: Optional[int] = None
    title: str
    date_time: str
    master: str
    location: str
    location_url: Optional[str] = ""
    cost: str
    duration: str
    max_slots: int
    photo_url: Optional[str] = ""
    players: List[PlayerEntry] = []
    reserve: List[PlayerEntry] = []
    telegram_message_id: Optional[int] = None

db_games: List[GameModel] = []

def sync_with_telegram(game: GameModel):
    try:
        direct_link = f"https://t.me/{BOT_USERNAME}/{APP_NAME}?startapp=game_{game.id}"
        
        p_list = "\n".join([f"{i+1}. {p.name} — {p.tg_profile}" for i, p in enumerate(game.players)]) or "Пока нет игроков"
        r_list = "\n*Резерв:*\n" + "\n".join([f"- {p.name}" for p in game.reserve]) if game.reserve else ""

        text = (
            f"🔥 *{game.title}*\n"
            f"🕒 Когда: {game.date_time}\n"
            f"📍 Место: {game.location}\n"
            f"👥 Свободно: {max(0, game.max_slots - len(game.players))}\n\n"
            f"📋 *Список:*\n{p_list}{r_list}\n\n"
            f"👉 [ЗАПИСАТЬСЯ]({direct_link})"
        )

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/"
        if not game.telegram_message_id:
            res = requests.post(url + "sendMessage", json={"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown"}).json()
            if res.get("ok"): game.telegram_message_id = res["result"]["message_id"]
        else:
            requests.post(url + "editMessageText", json={"chat_id": GROUP_ID, "message_id": game.telegram_message_id, "text": text, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Ошибка ТГ: {e}")

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
            if any(x.user_id == p.user_id for x in g.players + g.reserve): raise HTTPException(400, "Already signed")
            if len(g.players) < g.max_slots: g.players.append(p)
            else: g.reserve.append(p)
            sync_with_telegram(g)
            return {"status": "ok"}
    raise HTTPException(404, "Not found")

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
