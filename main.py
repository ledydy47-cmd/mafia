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
import sqlite3
import json
from PIL import Image
import io

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

BOT_TOKEN = "8794090676:AAHS-qb5r5OyNQaFq1xF3uwXh7tOFFqosXs"
GROUP_ID = "-1003932633365"
BOT_USERNAME = "mafia_revolutionclub_bot"
APP_NAME = "app"
DB_PATH = "database.db"

# ══ БАЗА ДАННЫХ ══
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, game_date TEXT, game_day TEXT,
            table_type TEXT, description TEXT,
            fits TEXT, not_fits TEXT, time_start TEXT,
            games_count TEXT, cost TEXT, master TEXT,
            location_name TEXT, location_address TEXT,
            location_url TEXT, photo_url TEXT,
            max_slots INTEGER DEFAULT 15,
            players TEXT DEFAULT '[]',
            reserve TEXT DEFAULT '[]',
            telegram_message_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def db_get_all_games():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM games ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    result = []
    for row in rows:
        g = dict(row)
        g['players'] = json.loads(g['players'])
        g['reserve']  = json.loads(g['reserve'])
        result.append(g)
    return result

def db_get_game(game_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM games WHERE id=?", (game_id,))
    row = c.fetchone()
    conn.close()
    if not row: return None
    g = dict(row)
    g['players'] = json.loads(g['players'])
    g['reserve']  = json.loads(g['reserve'])
    return g

def db_save_game(game: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO games (title, game_date, game_day, table_type, description,
            fits, not_fits, time_start, games_count, cost, master,
            location_name, location_address, location_url, photo_url,
            max_slots, players, reserve, telegram_message_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        game['title'], game['game_date'], game['game_day'], game['table_type'],
        game['description'], game['fits'], game['not_fits'], game['time_start'],
        game['games_count'], game['cost'], game['master'], game['location_name'],
        game['location_address'], game['location_url'], game['photo_url'],
        game.get('max_slots', 15),
        json.dumps(game.get('players', []), ensure_ascii=False),
        json.dumps(game.get('reserve', []), ensure_ascii=False),
        game.get('telegram_message_id')
    ))
    game_id = c.lastrowid
    conn.commit()
    conn.close()
    return game_id

def db_update_game(game: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE games SET
            title=?, game_date=?, game_day=?, table_type=?, description=?,
            fits=?, not_fits=?, time_start=?, games_count=?, cost=?, master=?,
            location_name=?, location_address=?, location_url=?, photo_url=?,
            max_slots=?, players=?, reserve=?, telegram_message_id=?
        WHERE id=?
    ''', (
        game['title'], game['game_date'], game['game_day'], game['table_type'],
        game['description'], game['fits'], game['not_fits'], game['time_start'],
        game['games_count'], game['cost'], game['master'], game['location_name'],
        game['location_address'], game['location_url'], game['photo_url'],
        game.get('max_slots', 15),
        json.dumps(game.get('players', []), ensure_ascii=False),
        json.dumps(game.get('reserve', []), ensure_ascii=False),
        game.get('telegram_message_id'),
        game['id']
    ))
    conn.commit()
    conn.close()

def db_delete_game(game_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM games WHERE id=?", (game_id,))
    conn.commit()
    conn.close()

# ══ МОДЕЛИ ══
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

# ══ TELEGRAM ══
def sync_with_telegram(game: dict):
    try:
        direct_link = f"https://t.me/{BOT_USERNAME}/{APP_NAME}?startapp=game_{game['id']}"

        p_list = ""
        players = game.get('players', [])
        for i in range(1, 16):
            if i <= len(players):
                p = players[i-1]
                nick = f" «{p['nickname']}»" if p.get('nickname', '').strip() else ""
                tg = f" @{p['tg_profile'].replace('@','')}" if p['tg_profile'] != "нет" else ""
                p_list += f"{i}) {p['name']}{nick}{tg}\n"
            else:
                p_list += f"{i})\n"

        fits_f     = "\n".join([f"{x.strip()} ✅" for x in game['fits'].split(',') if x.strip()])
        not_fits_f = "\n".join([f"{x.strip()} ❌" for x in game['not_fits'].split(',') if x.strip()])

        text = (
            f"📅 *{game['game_date']}, {game['table_type']}*\n\n"
            f"*{game['title']}*\n\n"
            f"{game['description']}\n\n"
            f"*{game['title']}*\n"
            f"Подходит:\n{fits_f}\n\n"
            f"Не подходит:\n{not_fits_f}\n\n"
            f"*{game['game_date'].upper()}, {game['game_day']}*\n"
            f"*{game['time_start']}*\n"
            f"*{game['games_count']}*\n"
            f"*{game['cost']}*\n\n"
            f"Ведущий: {game['master']}\n\n"
            f"*Локация*\n"
            f"{game['location_name']}\n{game['location_address']}\n"
            f"{game['location_url']}\n\n"
            f"*Участники:*\n"
            f"{p_list}"
            f"\n👉 [ЗАПИСЬ]({direct_link})"
        )

        tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/"

        if game['photo_url'] and not game['telegram_message_id']:
            filename = game['photo_url'].split("/uploads/")[-1]
            filepath = os.path.join(UPLOAD_DIR, filename)
            print(f"[TG] Читаем файл с диска: {filepath}")

            with open(filepath, "rb") as f:
                raw = f.read()

            img = Image.open(io.BytesIO(raw))
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            jpeg_buffer = io.BytesIO()
            img.save(jpeg_buffer, format="JPEG", quality=90)
            jpeg_bytes = jpeg_buffer.getvalue()
            print(f"[TG] JPEG размер: {len(jpeg_bytes)} байт")

            files = {"photo": ("photo.jpg", jpeg_bytes, "image/jpeg")}
            data  = {"chat_id": GROUP_ID, "caption": text, "parse_mode": "Markdown"}
            res   = requests.post(tg_url + "sendPhoto", data=data, files=files)

        elif game['photo_url'] and game['telegram_message_id']:
            payload = {
                "chat_id": GROUP_ID,
                "message_id": game['telegram_message_id'],
                "caption": text,
                "parse_mode": "Markdown"
            }
            res = requests.post(tg_url + "editMessageCaption", json=payload)

        else:
            payload = {
                "chat_id": GROUP_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }
            if game['telegram_message_id']:
                payload["message_id"] = game['telegram_message_id']
                method = "editMessageText"
            else:
                method = "sendMessage"
            res = requests.post(tg_url + method, json=payload)

        print(f"[TG] Статус: {res.status_code} | Ответ: {res.text}")

        res_json = res.json()
        if res_json.get("ok") and not game['telegram_message_id']:
            game['telegram_message_id'] = res_json["result"]["message_id"]
            print(f"[TG] message_id сохранён: {game['telegram_message_id']}")
        elif not res_json.get("ok"):
            print(f"[TG] ОШИБКА: {res_json.get('description')}")

    except Exception as e:
        print(f"[TG] ИСКЛЮЧЕНИЕ: {e}")

def delete_telegram_message(message_id: int):
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
            json={"chat_id": GROUP_ID, "message_id": message_id}
        )
        print(f"[TG] Удаление поста: {res.text}")
    except Exception as e:
        print(f"[TG] Ошибка удаления: {e}")

# ══ ЭНДПОИНТЫ ══
@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

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

@app.get("/games")
async def get_games():
    return db_get_all_games()

@app.post("/add_game")
async def add_game(game: GameModel):
    g = game.dict()
    g['players'] = []
    g['reserve']  = []
    g['telegram_message_id'] = None
    game_id = db_save_game(g)
    g['id'] = game_id
    sync_with_telegram(g)
    # Сохраняем telegram_message_id обратно в БД
    db_update_game(g)
    return {"status": "ok", "id": game_id}

@app.post("/edit_game/{game_id}")
async def edit_game(game_id: int, game: GameModel):
    existing = db_get_game(game_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Игра не найдена")
    updated = game.dict()
    updated['id'] = game_id
    updated['players'] = existing['players']
    updated['reserve']  = existing['reserve']
    updated['telegram_message_id'] = existing['telegram_message_id']
    # Если фото не изменилось — оставляем старое
    if not updated['photo_url']:
        updated['photo_url'] = existing['photo_url']
    db_update_game(updated)
    sync_with_telegram(updated)
    db_update_game(updated)
    return {"status": "ok"}

@app.post("/register/{game_id}")
async def register(game_id: int, p: PlayerEntry):
    g = db_get_game(game_id)
    if not g: return {"status": "error"}
    if any(x['user_id'] == p.user_id for x in g['players'] + g['reserve']):
        return {"status": "exists"}
    if len(g['players']) < g['max_slots']:
        g['players'].append(p.dict())
    else:
        g['reserve'].append(p.dict())
    db_update_game(g)
    sync_with_telegram(g)
    db_update_game(g)
    return {"status": "ok"}

@app.post("/cancel/{game_id}")
async def cancel(game_id: int, user_id: int):
    g = db_get_game(game_id)
    if not g: return {"status": "error"}
    g['players'] = [p for p in g['players'] if p['user_id'] != user_id]
    g['reserve']  = [p for p in g['reserve']  if p['user_id'] != user_id]
    if len(g['players']) < g['max_slots'] and g['reserve']:
        g['players'].append(g['reserve'].pop(0))
    db_update_game(g)
    sync_with_telegram(g)
    db_update_game(g)
    return {"status": "ok"}

@app.delete("/delete_game/{game_id}")
async def delete_game(game_id: int):
    g = db_get_game(game_id)
    if not g: raise HTTPException(status_code=404, detail="Игра не найдена")
    # Удаляем пост в Telegram
    if g['telegram_message_id']:
        delete_telegram_message(g['telegram_message_id'])
    # Удаляем фото с диска
    if g['photo_url']:
        try:
            filename = g['photo_url'].split("/uploads/")[-1]
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Ошибка удаления файла: {e}")
    db_delete_game(game_id)
    return {"status": "deleted"}
