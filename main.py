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

# --- ТВОИ ДАННЫЕ (УЖЕ ВПИСАНЫ) ---
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
    master: str = "Не указан"
    location: str
    location_url: Optional[str] = ""
    cost: str = "Не указана"
    duration: str = "Не указано"
    max_slots: int
    photo_url: Optional[str] = ""
    players: List[PlayerEntry] = []
    reserve: List[PlayerEntry] = []
    telegram_message_id: Optional[int] = None

db_games: List[GameModel] = []

def sync_with_telegram(game: GameModel):
    """Отправка и обновление поста в Telegram"""
    try:
        # Ссылка на конкретную игру
        direct_link = f"https://t.me/{BOT_USERNAME}/{APP_NAME}?startapp=game_{game.id}"
        
        # Список участников (нумерованный)
        p_list = ""
        for i, p in enumerate(game.players):
            p_list += f"{i+1}. {p.name} {f'({p.nickname})' if p.nickname else ''} — {p.tg_profile}\n"
        if not p_list: p_list = "Пока никого нет"

        # Список резерва
        r_list = ""
        if game.reserve:
            r_list = "\n*Резерв:*\n" + "\n".join([f"- {p.name}" for p in game.reserve])

        # Текст поста
        text = (
            f"🔥 *{game.title}*\n\n"
            f"📅 Когда: {game.date_time}\n"
            f"🎙 Ведущий: {game.master}\n"
            f"📍 Место: [{game.location}]({game.location_url})\n"
            f"💰 Стоимость: {game.cost}\n"
            f"👥 Свободно мест: {max(0, game.max_slots - len(game.players))}\n\n"
            f"📋 *Список участников:*\n{p_list}"
            f"{r_list}\n\n"
            f"👉 [ЗАПИСАТЬСЯ НА ИГРУ]({direct_link})"
        )

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/"
        
        if not game.telegram_message_id:
            # Создание нового поста
            payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": False}
            res = requests.post(url + "sendMessage", json=payload, timeout=10).json()
            if res.get("ok"):
                game.telegram_message_id = res["result"]["message_id"]
            else:
                print(f"Ошибка ТГ: {res.get('description')}")
        else:
            # Обновление существующего поста
            payload = {"chat_id": GROUP_ID, "message_id": game.telegram_message_id, "text": text, "parse_mode": "Markdown"}
            requests.post(url + "editMessageText", json=payload, timeout=10)

    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/games")
async def get_games():
    return db_games

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
            all_p = g.players + g.reserve
            if any(x.user_id == p.user_id for x in all_p):
                return {"status": "already_signed"}
            if len(g.players) < g.max_slots:
                g.players.append(p)
            else:
                g.reserve.append(p)
            sync_with_telegram(g)
            return {"status": "ok"}
    raise HTTPException(404)

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
