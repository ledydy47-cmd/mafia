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
    title: str # Название игры
    game_date: str # 10 мая
    game_day: str # Воскресенье
    table_type: str # Вайбовый стол
    description: str # Текст про экватор мая...
    fits: str # Список через запятую
    not_fits: str # Список через запятую
    time_start: str # 18:00
    games_count: str # Четыре игры
    cost: str # 800 рублей
    master: str # Актриса Таисия
    location_name: str # Парадная
    location_address: str # Малые Каменщики 16...
    location_url: str # https://...
    photo_url: Optional[str] = ""
    max_slots: int = 15
    players: List[PlayerEntry] = []
    reserve: List[PlayerEntry] = []
    telegram_message_id: Optional[int] = None

db_games: List[GameModel] = []

def sync_with_telegram(game: GameModel):
    try:
        direct_link = f"https://t.me/{BOT_USERNAME}/{APP_NAME}?startapp=game_{game.id}"
        
        # Список участников 1-15
        p_list = ""
        for i in range(1, 16):
            if i <= len(game.players):
                p = game.players[i-1]
                tg = f" @{p.tg_profile.replace('@','')}" if p.tg_profile != "нет" else ""
                p_list += f"{i}) {p.name}{tg}\n"
            else:
                p_list += f"{i})\n"

        # Форматирование списков Подходит/Не подходит
        fits_formatted = "\n".join([f"{x.strip()} ✅" for x in game.fits.split(',') if x.strip()])
        not_fits_formatted = "\n".join([f"{x.strip()} ❌" for x in game.not_fits.split(',') if x.strip()])

        # Сборка текста поста по твоему шаблону
        text = (
            f"📅 *{game.game_date}, {game.table_type}*\n\n"
            f"*{game.title}*\n\n"
            f"{game.description}\n\n"
            f"*{game.title}*\n"
            f"Подходит:\n{fits_formatted}\n\n"
            f"Не подходит:\n{not_fits_formatted}\n\n"
            f"*{game.game_date.upper()}, {game.game_day}*\n"
            f"*{game.time_start}*\n"
            f"*{game.games_count}*\n"
            f"*{game.cost}*\n\n"
            f"Ведущий: {game.master}\n\n"
            f"*Локация*\n"
            f"{game.location_name}, {game.location_address}\n"
            f"{game.location_url}\n\n"
            f"*Участники:*\n"
            f"{p_list}"
            f"\n👉 [ЗАПИСЬ]({direct_link})"
        )

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/"
        method = "sendPhoto" if game.photo_url else "sendMessage"
        
        payload = {"chat_id": GROUP_ID, "parse_mode": "Markdown"}
        if game.photo_url:
            payload.update({"photo": game.photo_url, "caption": text})
        else:
            payload.update({"text": text, "disable_web_page_preview": False})

        if not game.telegram_message_id:
            res = requests.post(url + method, json=payload).json()
            if res.get("ok"): game.telegram_message_id = res["result"]["message_id"]
        else:
            m = "editMessageCaption" if game.photo_url else "editMessageText"
            payload["message_id"] = game.telegram_message_id
            requests.post(url + m, json=payload)
    except Exception as e: print(f"TG Error: {e}")

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
