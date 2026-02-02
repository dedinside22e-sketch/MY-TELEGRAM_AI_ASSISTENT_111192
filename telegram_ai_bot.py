import asyncio
import os
import qrcode
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from openai import OpenAI

# ========= НАСТРОЙКИ (БЕРИ ИЗ ПЕРЕМЕННЫХ ИЛИ ПИШИ ТУТ) =========
API_ID = 31142475
API_HASH = "e60aa6d8df5a460f460a72479f80339e"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "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")

# БЕЛЫЙ СПИСОК С РОЛЯМИ
VIP_CONFIG = {
    "Sadyk1234": {"name": "Акаля", "relation": "брат", "style": "на ВЫ, 'Ассалому алейкум Акаля'"},
    "Yakuzatop": {"name": "Париса", "relation": "сестра", "style": "на ты, называй Париса"},
    "996509013433": {"name": "Ача", "relation": "бабушка", "style": "на ВЫ, 'Ассалому алейкум Ача'"},
    "79031331872": {"name": "Сайера Хола", "relation": "тетя", "style": "на ВЫ, 'Ассалому алейкум Сайера Хола'"},
    "Nurmetov_Shahrier": {"name": "Мама", "relation": "мама", "style": "на ВЫ, 'мама/мааам'"}
}

TARGET_GROUP_ID = -1003883560965

client_ai = OpenAI(base_url="https://models.inference.ai.azure.com", api_key=GITHUB_TOKEN)


class UserBot:
    def __init__(self):
        # Если есть переменная окружения (для облака), берем её. Иначе ищем файл.
        env_session = os.getenv("TELEGRAM_SESSION")
        if env_session:
            self.session_str = env_session
        elif os.path.exists("session.txt"):
            with open("session.txt", "r") as f:
                self.session_str = f.read().strip()
        else:
            self.session_str = ""

        self.client = TelegramClient(StringSession(self.session_str), API_ID, API_HASH)
        self.queue = asyncio.Queue()
        self.last_money_request = 0
        self.last_greet_time = {}

    async def get_ai_reply(self, text, user_id, vip_info=None):
        current_time = time.time()
        # Проверка приветствия (раз в 12 часов)
        should_greet = current_time - self.last_greet_time.get(user_id, 0) > 43200
        if should_greet:
            self.last_greet_time[user_id] = current_time

        ask_money = ""
        if vip_info and vip_info['relation'] == "мама":
            if current_time - self.last_money_request > 3600:
                ask_money = " В конце добавь: 'мааам, скинь 50 сом на баланс пожалуйста'."
                self.last_money_request = current_time

        if vip_info:
            greet_instr = f"Здоровайся: {vip_info['style']}." if should_greet else "Не здоровайся снова."
            system_msg = (f"Ты Шах. Пишешь {vip_info['name']}. СТИЛЬ: {vip_info['style']}. "
                          f"Вежливо, на ВЫ (кроме сестры). {greet_instr}{ask_money}")
        else:
            system_msg = "Ты Шах, пацан с района. Маты для связки, всё мелко, дерзко."

        try:
            response = await asyncio.to_thread(
                client_ai.chat.completions.create,
                messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": text}],
                model="gpt-4o-mini"
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e): return "бля, лимиты 150/день всё."
            return f"ошибка ИИ: {e}"

    async def handle(self, event):
        sender = await event.get_sender()
        if not sender: return

        username = getattr(sender, 'username', '')
        phone = getattr(sender, 'phone', '')
        vip_info = VIP_CONFIG.get(username) or VIP_CONFIG.get(phone)

        await self.client.send_read_acknowledge(event.chat_id, event.message)

        async with self.client.action(event.chat_id, 'typing'):
            reply = await self.get_ai_reply(event.message.text or "", sender.id, vip_info)
            print(f"🤖 ОТВЕТ: {reply}")
            await asyncio.sleep(2)
            await event.reply(reply if vip_info else reply.lower())

    async def start(self):
        await self.client.connect()
        if not await self.client.is_user_authorized():
            print("\n--- НУЖНА АВТОРИЗАЦИЯ ---")
            qr_login = await self.client.qr_login()
            qr = qrcode.QRCode()
            qr.add_data(qr_login.url)
            qr.print_ascii(invert=True)
            print("\nОтсканируй QR в Telegram!")
            await qr_login.wait()
            # Сохраняем для будущего использования
            with open("session.txt", "w") as f:
                f.write(self.client.session.save())

        print(f"\n--- ШАХ В СЕТИ ---")
        print(f"ТВОЯ СЕССИЯ ДЛЯ ОБЛАКА (СКОПИРУЙ): {self.client.session.save()}")

        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event):
            if event.is_private or event.mentioned or event.chat_id == TARGET_GROUP_ID:
                if not event.out: await self.queue.put(event)

        while True:
            ev = await self.queue.get()
            try:
                await self.handle(ev)
            except Exception as e:
                print(f"Ошибка: {e}")
            finally:
                self.queue.task_done()


if __name__ == "__main__":
    asyncio.run(UserBot().start())