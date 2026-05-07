from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os
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
    description: Optional[str] = "" # Новое поле для "Вайбового описания"
    master: str = ""
    location: str = ""
    location_url: Optional[str] = ""
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
        
        # Формируем нумерованный список участников (всегда 15 строк)
        players_list = ""
        for i in range(1, 16):
            if i <= len(game.players):
                p = game.players[i-1]
                tg = f" @{p.tg_profile.replace('@','')}" if p.tg_profile != "нет" else ""
                nick = f" {p.nickname}" if p.nickname else ""
                players_list += f"{i}) {p.name}{nick}{tg}\n"
            else:
                players_list += f"{i})\n"

        reserve_list = ""
        if game.reserve:
            reserve_list = "\n*Резерв:*\n" + "\n".join([f"- {p.name}" for p in game.reserve])

        # Сборка красивого поста по твоему формату
        text = (
            f"*{game.date_time}, {game.title}*\n\n"
            f"{game.description}\n\n"
            f"📅 {game.date_time.upper()}\n"
            f"⏰ {game.duration}\n"
            f"💰 {game.cost}\n\n"
            f"🎙 Ведущий: {game.master}\n\n"
            f"📍 *Локация*\n"
            f"{game.location}\n"
            f"{game.location_url}\n\n"
            f"*Участники:*\n"
            f"{players_list}"
            f"{reserve_list}\n"
            f"👉 [ЗАПИСЬ]({direct_link})"
        )

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/"
        
        if not game.telegram_message_id:
            # Если есть ссылка на фото, шлем фото, иначе текст
            if game.photo_url:
                payload = {"chat_id": GROUP_ID, "photo": game.photo_url, "caption": text, "parse_mode": "Markdown"}
                res = requests.post(url + "sendPhoto", json=payload).json()
            else:
                payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": False}
                res = requests.post(url + "sendMessage", json=payload).json()
            
            if res.get("ok"):
                game.telegram_message_id = res["result"]["message_id"]
        else:
            if game.photo_url:
                payload = {"chat_id": GROUP_ID, "message_id": game.telegram_message_id, "caption": text, "parse_mode": "Markdown"}
                requests.post(url + "editMessageCaption", json=payload)
            else:
                payload = {"chat_id": GROUP_ID, "message_id": game.telegram_message_id, "text": text, "parse_mode": "Markdown"}
                requests.post(url + "editMessageText", json=payload)

    except Exception as e:
        print(f"Ошибка: {e}")

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
