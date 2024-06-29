import json
import requests
from loguru import logger
from . import model
import pathlib
import hashlib


class Bot3P:
    def __init__(self, player_id: int):
        self.player_id = player_id
        model_path = pathlib.Path(__file__).parent / f"mortal.pth"
        self.model = model.load_model(player_id)
        with open(model_path, "rb") as f:
            self.model_hash = hashlib.sha256(f.read()).hexdigest()
        self.online = False

    def react(self, events: str) -> str:
        events = json.loads(events)

        return_action = None
        for e in events:
            return_action = self.model.react(json.dumps(e, separators=(",", ":")))

        if return_action is None:
            return json.dumps({"type": "none"}, separators=(",", ":"))
        else:
            raw_data = json.loads(return_action)
            if self.online:
                raw_data["online"] = model.online_valid
            return json.dumps(raw_data, separators=(",", ":"))

    def state(self):
        return self.model.state


class EngineRuntimeError(Exception):
    def __init__(self, msg: str, player_id: int) -> None:
        self.msg = msg
        self.player_id = player_id


class TimeoutExpired(Exception):
    def __init__(self, player_id: int) -> None:
        self.player_id = player_id


class MjaiPlayerClient:
    def __init__(
        self,
    ) -> None:
        self.player_id = 0

        self.bot = None

    def launch_bot(self, player_id: int, is_3p=False) -> None:
        self.player_id = player_id
        if is_3p:
            self.bot = Bot3P(player_id)
        else:
            raise NotImplementedError("4p bot is not implemented")

    def delete_bot(self):
        self.bot = None

    def restart_bot(self, player_id: int, is_3p=False) -> None:
        self.delete_bot()
        self.launch_bot(player_id, is_3p)

    def react(self, events: str) -> str:
        if self.bot is None:
            raise ValueError("bot is not running (3)")

        try:
            input_data = events.encode("utf8")

            logger.debug(f"{self.player_id} <- {input_data}")
            outs = self.bot.react(input_data)
            logger.debug(f"{self.player_id} -> {outs}")

            if (
                json.loads(events)[-1]["type"] == "tsumo"
                and json.loads(events)[-1]["actor"] == self.player_id
            ):
                json_data = {}
                try:
                    json_data = json.loads(outs)
                except Exception:
                    raise RuntimeError(f"JSON parser error: {outs}")

                if json_data["type"] == "none":
                    raise RuntimeError(f"invalid response: {str(outs)}")

        except requests.Timeout:
            raise TimeoutExpired(self.player_id)
        except Exception as e:
            raise EngineRuntimeError(f"RuntimeError: {str(e)}", self.player_id)

        return outs
