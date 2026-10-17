"""CAMBC entry point for Alpha Bot."""
import cambc
import draft
from bot import Bot


def main():
    bot = Bot()
    while True:
        try:
            if cambc.is_draft():
                draft.play()
            else:
                bot.play_turn()
        except Exception as error:
            print(f"bot error: {error}", flush=True)
        cambc.end_turn()


if __name__ == "__main__":
    main()
