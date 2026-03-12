import asyncio
from aiogram import Bot

async def test_token(token):
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        print(f"Token is valid! Bot name: {me.full_name}, username: @{me.username}")
    except Exception as e:
        print(f"Token is invalid: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    import sys
    token = sys.argv[1] if len(sys.argv) > 1 else "8305690828:AAHiFagf5FlevbWDThKyZmlepf_l39Y8ahU"
    asyncio.run(test_token(token))
