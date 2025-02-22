import asyncio
from telegram import Bot

async def test_bot():
    bot = Bot(token="7873086292:AAEthtBcUFopzyKY5a3UPBlGdNzP5BrDBIM")
    try:
        await bot.send_message(chat_id="7882172599", text="테스트 메시지입니다.")
        print("메시지 전송 성공!")
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    asyncio.run(test_bot()) 