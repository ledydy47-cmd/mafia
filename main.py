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

# --- НАСТРОЙКИ ТЕЛЕГРАМ ---
BOT_TOKEN = "8794090676:AAHS-qb5r5OyNQaFq1xF3uwXh7tOFFqosXs"
GROUP_ID = "-1003932633365" # Например, "-1002111239214"
BOT_USERNAME = "mafia_revolutionclub_bot" # Например, "mafia_bot" без @
APP_NAME = "app" # То, что вы вводили в BotFather для приложения

# Модели данных
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
    telegram_message_id: Optional[int] = None # ID поста в группе

db_games: List[GameModel] = []

# --- ФУНКЦИЯ СИНХРОНИЗАЦИИ С ТЕЛЕГРАМ ---
def sync_with_telegram(game: GameModel):
    # Прямая ссылка на конкретную игру
    direct_link = f"https://t.me/{BOT_USERNAME}/{APP_NAME}?startapp=game_{game.id}"
    
    # Формируем список участников
    players_list = ""
    for i, p in enumerate(game.players):
        players_list += f"{i+1}. {p.name} {f'({p.nickname})' if p.nickname else ''} — {p.tg_profile}\n"
    if not players_list: players_list = "Пока никого нет"

    reserve_list = ""
    if game.reserve:
        reserve_list = "\n*Резерв:*\n" + "\n".join([f"- {p.name}" for p in game.reserve])

    # Текст сообщения
    text = (
        f"🔥 *{game.title}*\n\n"
        f"📅 *Когда:* {game.date_time}\n"
        f"🎙 *Ведущий:* {game.master}\n"
        f"📍 *Место:* [{game.location}]({game.location_url})\n"
        f"⏳ *Игр:* {game.duration}\n"
        f"💰 *Стоимость:* {game.cost}\n"
        f"👥 *Свободно мест:* {max(0, game.max_slots - len(game.players))}\n\n"
        f"📋 *Список игроков:*\n{players_list}"
        f"{reserve_list}\n\n"
        f"👉 [ЗАПИСАТЬСЯ НА ЭТУ ИГРУ]({direct_link})"
    )

    if not game.telegram_message_id:
        # Отправляем новый пост (если есть фото - с фото, если нет - текстом)
        if game.photo_url:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            payload = {"chat_id": GROUP_ID, "photo": game.photo_url, "caption": text, "parse_mode": "Markdown"}
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": False}
        
        res = requests.post(url, json=payload).json()
        if res.get("ok"):
            game.telegram_message_id = res["result"]["message_id"]
    else:
        # Редактируем существующий пост
        if game.photo_url:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageCaption"
            payload = {"chat_id": GROUP_ID, "message_id": game.telegram_message_id, "caption": text, "parse_mode": "Markdown"}
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
            payload = {"chat_id": GROUP_ID, "message_id": game.telegram_message_id, "text": text, "parse_mode": "Markdown"}
        
        requests.post(url, json=payload)

# --- ЭНДПОИНТЫ API ---

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
    sync_with_telegram(game) # Создаем пост в ТГ
    return {"status": "success"}

@app.post("/edit_game/{game_id}")
async def edit_game(game_id: int, updated_game: GameModel):
    for i, game in enumerate(db_games):
        if game.id == game_id:
            updated_game.id = game_id
            updated_game.players = game.players
            updated_game.reserve = game.reserve
            updated_game.telegram_message_id = game.telegram_message_id
            db_games[i] = updated_game
            sync_with_telegram(db_games[i]) # Обновляем пост
            return {"status": "updated"}
    raise HTTPException(status_code=404, detail="Game not found")

@app.post("/register/{game_id}")
async def register(game_id: int, p: PlayerEntry):
    for game in db_games:
        if game.id == game_id:
            all_p = game.players + game.reserve
            if any(x.user_id == p.user_id for x in all_p):
                raise HTTPException(status_code=400, detail="Already signed")
            if len(game.players) < game.max_slots:
                game.players.append(p)
            else:
                game.reserve.append(p)
            sync_with_telegram(game) # Обновляем пост при записи
            return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Not found")

@app.post("/cancel/{game_id}")
async def cancel(game_id: int, user_id: int):
    for game in db_games:
        if game.id == game_id:
            game.players = [p for p in game.players if p.user_id != user_id]
            game.reserve = [p for p in game.reserve if p.user_id != user_id]
            if len(game.players) < game.max_slots and game.reserve:
                game.players.append(game.reserve.pop(0))
            sync_with_telegram(game) # Обновляем пост при отмене
            return {"status": "ok"}
    return {"status": "error"}

@app.delete("/delete_game/{game_id}")
async def delete_game(game_id: int):
    global db_games
    # Опционально: можно удалять сообщение из ТГ при удалении игры
    db_games = [g for g in db_games if g.id != game_id]
    return {"status": "deleted"}
