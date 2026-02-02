import asyncio
import os
import time
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from openai import OpenAI

# ========= НАСТРОЙКИ =========
API_ID = 31142475
API_HASH = "e60aa6d8df5a460f460a72479f80339e"

# ВАШ НОВЫЙ КЛЮЧ OPENAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Фейковый сервер для Render
app = Flask('')

@app.route('/')
def home(): return "Бот Шах онлайн!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

VIP_CONFIG = {
    "Sadyk1234": {"name": "Акаля", "relation": "брат", "style": "на ВЫ, 'Ассалому алейкум Акаля'"},
    "Yakuzatop": {"name": "Париса", "relation": "сестра", "style": "на ты, называй Париса"},
    "996509013433": {"name": "Ача", "relation": "бабушка", "style": "на ВЫ, 'Ассалому алейкум Ача'"},
    "79031331872": {"name": "Сайера Хола", "relation": "тетя", "style": "на ВЫ, 'Ассалому алейкум Сайера Хола'"},
    "Nurmetov_Shahrier": {"name": "Мама", "relation": "мама", "style": "на ВЫ, 'мааам'"}
}

TARGET_GROUP_ID = -1003883560965

# Подключаемся к официальному API OpenAI с новым ключом
client_ai = OpenAI(api_key=OPENAI_API_KEY)


class UserBot:
    def __init__(self):
        # Ищем сессию в переменных окружения
        self.session_str = os.getenv("TELEGRAM_SESSION", "")
        self.client = TelegramClient(StringSession(self.session_str), API_ID, API_HASH)
        self.queue = asyncio.Queue()
        self.last_money_request = 0
        self.last_greet_time = {}

    async def get_ai_reply(self, text, user_id, vip_info=None):
        current_time = time.time()
        should_greet = current_time - self.last_greet_time.get(user_id, 0) > 43200
        if should_greet: self.last_greet_time[user_id] = current_time

        ask_money = ""
        if vip_info and vip_info['relation'] == "мама":
            if current_time - self.last_money_request > 10800:
                ask_money = " В конце добавь: 'мааам, скинь 50 сом на баланс пожалуйста'."
                self.last_money_request = current_time

        if vip_info:
            greet_instr = f"Здоровайся: {vip_info['style']}." if should_greet else "Не здоровайся."
            system_msg = f"Ты Шах. Пишешь {vip_info['name']}. {vip_info['style']}. Вежливо. {greet_instr}{ask_money}"
        else:
            system_msg = "Ты Шах, пацан с района. Дерзко, мелко, маты для связки."

        try:
            response = await asyncio.to_thread(
                client_ai.chat.completions.create,
                messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": text}],
                model="gpt-4o-mini"
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            # Ошибка 429 у OpenAI часто означает окончание денег на счету
            if "429" in str(e): return "Лимиты OpenAI исчерпаны или нет денег."
            return f"ошибка ИИ: {e}"

    async def handle(self, event):
        sender = await event.get_sender()
        if not sender: return
        vip_info = VIP_CONFIG.get(getattr(sender, 'username', '')) or VIP_CONFIG.get(getattr(sender, 'phone', ''))

        async with self.client.action(event.chat_id, 'typing'):
            reply = await self.get_ai_reply(event.message.text or "", sender.id, vip_info)
            await asyncio.sleep(1)
            await event.reply(reply if vip_info else reply.lower())

    async def start(self):
        await self.client.connect()
        if not await self.client.is_user_authorized():
            print("--- СЕССИЯ НЕ НАЙДЕНА. ВХОДИМ... ---")
            await self.client.start()
            print("\n--- СКОПИРУЙ ЭТУ СТРОКУ И ВСТАВЬ В RENDER (TELEGRAM_SESSION) ---")
            print(self.client.session.save())
            print("--- КОНЕЦ СТРОКИ ---\n")

        print("\n--- БОТ ШАХ В СЕТИ ---")

        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event):
            if event.is_private or event.mentioned or event.chat_id == TARGET_GROUP_ID:
                if not event.out: await self.queue.put(event)

        while True:
            ev = await self.queue.get()
            try:
                await self.handle(ev)
            except:
                pass
            finally:
                self.queue.task_done()


if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(UserBot().start())