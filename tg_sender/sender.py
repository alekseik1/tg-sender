import os
import typing as tp

from dotenv import load_dotenv
from telethon.sync import TelegramClient

load_dotenv()

api_id = int(os.environ["API_ID"])
api_hash = os.environ["API_HASH"]


class HasStrProtocol(tp.Protocol):
    def __str__(self) -> str: ...


def send_messages(session: HasStrProtocol, msgs: list[tuple[str, str]]):
    with TelegramClient(str(session), api_id, api_hash) as client:
        for username, message in msgs:
            client.send_message(username, message)
