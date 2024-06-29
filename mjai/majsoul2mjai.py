import json
import time
from .player import MjaiPlayerClient
from .liqi import MsgType, LiqiProto
from functools import cmp_to_key
import numpy as np

MS_TILE_2_MJAI_TILE = {
    "0m": "5mr",
    "1m": "1m",
    "2m": "2m",
    "3m": "3m",
    "4m": "4m",
    "5m": "5m",
    "6m": "6m",
    "7m": "7m",
    "8m": "8m",
    "9m": "9m",
    "0p": "5pr",
    "1p": "1p",
    "2p": "2p",
    "3p": "3p",
    "4p": "4p",
    "5p": "5p",
    "6p": "6p",
    "7p": "7p",
    "8p": "8p",
    "9p": "9p",
    "0s": "5sr",
    "1s": "1s",
    "2s": "2s",
    "3s": "3s",
    "4s": "4s",
    "5s": "5s",
    "6s": "6s",
    "7s": "7s",
    "8s": "8s",
    "9s": "9s",
    "1z": "E",
    "2z": "S",
    "3z": "W",
    "4z": "N",
    "5z": "P",
    "6z": "F",
    "7z": "C",
}

MJAI_TILE_2_MS_TILE = {
    "5mr": "0m",
    "1m": "1m",
    "2m": "2m",
    "3m": "3m",
    "4m": "4m",
    "5m": "5m",
    "6m": "6m",
    "7m": "7m",
    "8m": "8m",
    "9m": "9m",
    "5pr": "0p",
    "1p": "1p",
    "2p": "2p",
    "3p": "3p",
    "4p": "4p",
    "5p": "5p",
    "6p": "6p",
    "7p": "7p",
    "8p": "8p",
    "9p": "9p",
    "5sr": "0s",
    "1s": "1s",
    "2s": "2s",
    "3s": "3s",
    "4s": "4s",
    "5s": "5s",
    "6s": "6s",
    "7s": "7s",
    "8s": "8s",
    "9s": "9s",
    "E": "1z",
    "S": "2z",
    "W": "3z",
    "N": "4z",
    "P": "5z",
    "F": "6z",
    "C": "7z",
}


class Operation:
    NoEffect = 0
    Discard = 1
    Chi = 2
    Peng = 3
    AnGang = 4
    MingGang = 5
    JiaGang = 6
    Liqi = 7
    Zimo = 8
    Hu = 9
    LiuJu = 10


class OperationChiPengGang:
    Chi = 0
    Peng = 1
    Gang = 2


class OperationAnGangAddGang:
    AnGang = 3
    AddGang = 2


class MajsoulBridge:
    def __init__(self) -> None:
        self.accountId = 0
        self.seat = 0
        self.mjai_message = []
        self.lastDiscard = None
        self.reach = False
        self.accept_reach = None
        self.operation = {}
        self.AllReady = False
        self.temp = {}
        self.doras = []
        self.my_tehais = ["?"] * 13
        self.my_tsumohai = "?"
        self.syncing = False

        self.mode_id = -1
        self.rank = -1
        self.score = -1

        self.mjai_client = MjaiPlayerClient()
        self.is_3p = False
        pass

    def input(self, parse_msg: dict) -> dict | None:
        # TODO SyncGame
        if (
            parse_msg["method"] == ".lq.FastTest.syncGame"
            or parse_msg["method"] == ".lq.FastTest.enterGame"
        ) and parse_msg["type"] == MsgType.Res:
            self.syncing = True
            syncGame_msgs = LiqiProto().parse_syncGame(parse_msg)
            reacts = []
            for msg in syncGame_msgs:
                reacts.append(self.input(msg))
            self.syncing = False
            if len(reacts) >= 1:
                return reacts[-1]
            else:
                return None

        # ready
        if (
            parse_msg["method"] == ".lq.FastTest.fetchGamePlayerState"
            and parse_msg["type"] == MsgType.Res
        ):
            # if parse_msg['data']['stateList'] == ['READY', 'READY', 'READY', 'READY']:
            self.AllReady = True
            return None
        # start_game
        if (
            parse_msg["method"] == ".lq.FastTest.authGame"
            and parse_msg["type"] == MsgType.Req
        ):
            self.__init__()
            self.accountId = parse_msg["data"]["accountId"]
        if (
            parse_msg["method"] == ".lq.FastTest.authGame"
            and parse_msg["type"] == MsgType.Res
        ):
            self.is_3p = len(parse_msg["data"]["seatList"]) == 3
            try:
                self.mode_id = parse_msg["data"]["gameConfig"]["meta"]["modeId"]
            except:
                self.mode_id = -1

            seatList = parse_msg["data"]["seatList"]
            self.seat = seatList.index(self.accountId)
            self.mjai_client.launch_bot(self.seat, self.is_3p)
            self.mjai_message.append({"type": "start_game", "id": self.seat})
            self.react(self.mjai_client)
            return None
        if parse_msg["method"] == ".lq.ActionPrototype":
            # start_kyoku
            if parse_msg["data"]["name"] == "ActionNewRound":
                self.AllReady = False
                bakaze = ["E", "S", "W", "N"][parse_msg["data"]["data"]["chang"]]
                dora_marker = MS_TILE_2_MJAI_TILE[parse_msg["data"]["data"]["doras"][0]]
                self.doras = [dora_marker]
                honba = parse_msg["data"]["data"]["ben"]
                oya = parse_msg["data"]["data"]["ju"]
                kyoku = oya + 1
                kyotaku = parse_msg["data"]["data"]["liqibang"]
                scores = parse_msg["data"]["data"]["scores"]
                if self.is_3p:
                    scores = scores + [0]
                tehais = [["?"] * 13] * 4
                my_tehais = ["?"] * 13
                for hai in range(13):
                    my_tehais[hai] = MS_TILE_2_MJAI_TILE[
                        parse_msg["data"]["data"]["tiles"][hai]
                    ]
                if len(parse_msg["data"]["data"]["tiles"]) == 13:
                    tehais[self.seat] = sorted(my_tehais, key=cmp_to_key(compare_pai))
                    self.mjai_message.append(
                        {
                            "type": "start_kyoku",
                            "bakaze": bakaze,
                            "dora_marker": dora_marker,
                            "honba": honba,
                            "kyoku": kyoku,
                            "kyotaku": kyotaku,
                            "oya": oya,
                            "scores": scores,
                            "tehais": tehais,
                        }
                    )
                elif len(parse_msg["data"]["data"]["tiles"]) == 14:
                    self.my_tsumohai = MS_TILE_2_MJAI_TILE[
                        parse_msg["data"]["data"]["tiles"][13]
                    ]
                    all_tehais = my_tehais + [self.my_tsumohai]
                    all_tehais = sorted(all_tehais, key=cmp_to_key(compare_pai))
                    tehais[self.seat] = all_tehais[:13]
                    self.mjai_message.append(
                        {
                            "type": "start_kyoku",
                            "bakaze": bakaze,
                            "dora_marker": dora_marker,
                            "honba": honba,
                            "kyoku": kyoku,
                            "kyotaku": kyotaku,
                            "oya": oya,
                            "scores": scores,
                            "tehais": tehais,
                        }
                    )
                    self.mjai_message.append(
                        {"type": "tsumo", "actor": self.seat, "pai": all_tehais[13]}
                    )
                else:
                    raise

            if self.accept_reach is not None:
                self.mjai_message.append(self.accept_reach)
                self.accept_reach = None

            # According to mjai.app, in the case of an ankan, the dora event comes first, followed by the tsumo event.
            if "data" in parse_msg["data"]:
                if "doras" in parse_msg["data"]["data"]:
                    if len(parse_msg["data"]["data"]["doras"]) > len(self.doras):
                        self.mjai_message.append(
                            {
                                "type": "dora",
                                "dora_marker": MS_TILE_2_MJAI_TILE[
                                    parse_msg["data"]["data"]["doras"][-1]
                                ],
                            }
                        )
                        self.doras = parse_msg["data"]["data"]["doras"]

            # tsumo
            if parse_msg["data"]["name"] == "ActionDealTile":
                actor = parse_msg["data"]["data"]["seat"]
                if parse_msg["data"]["data"]["tile"] == "":
                    pai = "?"
                else:
                    pai = MS_TILE_2_MJAI_TILE[parse_msg["data"]["data"]["tile"]]
                    self.my_tsumohai = pai
                self.mjai_message.append({"type": "tsumo", "actor": actor, "pai": pai})
            # dahai
            if parse_msg["data"]["name"] == "ActionDiscardTile":
                actor = parse_msg["data"]["data"]["seat"]
                self.lastDiscard = actor
                pai = MS_TILE_2_MJAI_TILE[parse_msg["data"]["data"]["tile"]]
                tsumogiri = parse_msg["data"]["data"]["moqie"]
                if parse_msg["data"]["data"]["isLiqi"]:
                    if parse_msg["data"]["data"]["seat"] == self.seat:
                        pass
                    else:
                        self.mjai_message.append({"type": "reach", "actor": actor})
                self.mjai_message.append(
                    {
                        "type": "dahai",
                        "actor": actor,
                        "pai": pai,
                        "tsumogiri": tsumogiri,
                    }
                )
                if parse_msg["data"]["data"]["isLiqi"]:
                    self.accept_reach = {"type": "reach_accepted", "actor": actor}
            # Reach
            if parse_msg["data"]["name"] == "ActionReach":
                # TODO
                pass
            # ChiPonKan
            if parse_msg["data"]["name"] == "ActionChiPengGang":
                actor = parse_msg["data"]["data"]["seat"]
                target = actor
                consumed = []
                pai = ""
                for idx, seat in enumerate(parse_msg["data"]["data"]["froms"]):
                    if seat != actor:
                        target = seat
                        pai = MS_TILE_2_MJAI_TILE[
                            parse_msg["data"]["data"]["tiles"][idx]
                        ]
                    else:
                        consumed.append(
                            MS_TILE_2_MJAI_TILE[parse_msg["data"]["data"]["tiles"][idx]]
                        )
                assert target != actor
                assert len(consumed) != 0
                assert pai != ""
                match parse_msg["data"]["data"]["type"]:
                    case OperationChiPengGang.Chi:
                        assert len(consumed) == 2
                        self.mjai_message.append(
                            {
                                "type": "chi",
                                "actor": actor,
                                "target": target,
                                "pai": pai,
                                "consumed": consumed,
                            }
                        )
                        pass
                    case OperationChiPengGang.Peng:
                        assert len(consumed) == 2
                        self.mjai_message.append(
                            {
                                "type": "pon",
                                "actor": actor,
                                "target": target,
                                "pai": pai,
                                "consumed": consumed,
                            }
                        )
                    case OperationChiPengGang.Gang:
                        assert len(consumed) == 3
                        self.mjai_message.append(
                            {
                                "type": "daiminkan",
                                "actor": actor,
                                "target": target,
                                "pai": pai,
                                "consumed": consumed,
                            }
                        )
                        pass
                    case _:
                        raise
            # AnkanKakan
            if parse_msg["data"]["name"] == "ActionAnGangAddGang":
                actor = parse_msg["data"]["data"]["seat"]
                match parse_msg["data"]["data"]["type"]:
                    case OperationAnGangAddGang.AnGang:
                        pai = MS_TILE_2_MJAI_TILE[parse_msg["data"]["data"]["tiles"]]
                        consumed = [pai.replace("r", "")] * 4
                        if pai[0] == "5" and pai[1] != "z":
                            consumed[0] += "r"
                        self.mjai_message.append(
                            {"type": "ankan", "actor": actor, "consumed": consumed}
                        )
                    case OperationAnGangAddGang.AddGang:
                        pai = MS_TILE_2_MJAI_TILE[parse_msg["data"]["data"]["tiles"]]
                        consumed = [pai.replace("r", "")] * 3
                        if pai[0] == "5" and not pai.endswith("r"):
                            consumed[0] = consumed[0] + "r"
                        self.mjai_message.append(
                            {
                                "type": "kakan",
                                "actor": actor,
                                "pai": pai,
                                "consumed": consumed,
                            }
                        )

            if parse_msg["data"]["name"] == "ActionBaBei":
                actor = parse_msg["data"]["data"]["seat"]
                self.mjai_message.append(
                    {"type": "nukidora", "actor": actor, "pai": "N"}
                )

            # hora
            if parse_msg["data"]["name"] == "ActionHule":
                # actor = parse_msg['data']['hules']['seat']
                # if parse_msg['data']['hules']['zimo']:
                #     target = actor
                # else:
                #     target = self.lastDiscard
                # pai = MS_TILE_2_MJAI_TILE[parse_msg['data']['hules']['huTile']]
                # self.mjai_message.append(
                #     {
                #         'type': 'hora',
                #         'actor': actor,
                #         'pai': pai
                #     }
                # )
                self.mjai_message = []
                self.mjai_message.append({"type": "end_kyoku"})
                self.react(self.mjai_client)
                return None
            # notile
            if parse_msg["data"]["name"] == "ActionNoTile":
                self.mjai_message = []
                self.mjai_message.append({"type": "end_kyoku"})
                self.react(self.mjai_client)
                return None
            # ryukyoku
            if parse_msg["data"]["name"] == "ActionLiuJu":
                # self.mjai_message.append(
                #     {
                #         'type': 'ryukyoku'
                #     }
                # )
                self.mjai_message = []
                self.mjai_message.append({"type": "end_kyoku"})
                self.react(self.mjai_client)
                return None

            if "data" in parse_msg["data"]:
                if "operation" in parse_msg["data"]["data"]:
                    self.operation = parse_msg["data"]["data"]["operation"]
                    return self.react(self.mjai_client)
        # end_game
        if (
            parse_msg["method"] == ".lq.NotifyGameEndResult"
            or parse_msg["method"] == ".lq.NotifyGameTerminate"
        ):
            # try:
            #     for idx, player in enumerate(parse_msg['data']['result']['players']):
            #         if player['seat'] == self.seat:
            #             self.rank = idx + 1
            #             self.score = player['partPoint1']
            #             game_result_log(self.mode_id, self.rank, self.score, self.mjai_client.bot.model_hash)
            # except:
            #     pass
            self.mjai_message.append({"type": "end_game"})
            self.react(self.mjai_client)
            self.mjai_client.restart_bot(self.seat, self.is_3p)
            return None
        return None

    def react(
        self, mjai_client: MjaiPlayerClient, overwrite: str | None = None
    ) -> dict:
        if overwrite is not None:
            # print(f"<- {overwrite}")
            out = mjai_client.react(
                str(overwrite)
                .replace("'", '"')
                .replace("True", "true")
                .replace("False", "false")
            )
        else:
            # print(f"<- {self.mjai_message}")
            out = mjai_client.react(
                str(self.mjai_message)
                .replace("'", '"')
                .replace("True", "true")
                .replace("False", "false")
            )
        self.mjai_message = []
        json_out = json.loads(out)
        if json_out["type"] == "reach":
            self.reach = True
            reach = [{"type": "reach", "actor": self.seat}]
            out = mjai_client.react(str(reach).replace("'", '"'))
            json_out = json.loads(out)
        return json_out

    def action(self, mjai_msg: dict | None, liqi: LiqiProto) -> bytes | None:
        if len(self.temp) != 0 and self.AllReady:
            temp = self.temp
            self.temp = {}
            time.sleep(3)
            return liqi.compose(temp)
        if mjai_msg is None:
            return None

        """
        data = {
            'id': msg_id, 
            'type': msg_type,
            'method': method_name, 
            'data': dict_obj
        }
        """
        # time.sleep(2)
        data = {}
        data["id"] = -1
        data["type"] = MsgType.Req
        data["method"] = ""
        data["data"] = {}
        match mjai_msg["type"]:
            case "none":
                # What if we canceled ron?
                data["method"] = ".lq.FastTest.inputChiPengGang"
                data["data"]["cancelOperation"] = True
                data["data"]["timeuse"] = 4
            case "dahai":
                data["method"] = ".lq.FastTest.inputOperation"
                data["data"]["type"] = Operation.Discard
                data["data"]["tile"] = MJAI_TILE_2_MS_TILE[mjai_msg["pai"]]
                data["data"]["moqie"] = mjai_msg["tsumogiri"]
                data["data"]["timeuse"] = 4
                if self.reach:
                    data["data"]["type"] = Operation.Liqi
                    self.reach = False
                    pass
            case "chi":
                data["method"] = ".lq.FastTest.inputChiPengGang"
                data["data"]["type"] = Operation.Chi
                data["data"]["index"] = -1
                data["data"]["timeuse"] = 4

                operation = next(
                    item
                    for item in self.operation["operationList"]
                    if item["type"] == Operation.Chi
                )
                mjai_consumed = mjai_msg["consumed"]
                mjai_consumed.sort()
                for idx, consumed in enumerate(operation["combination"]):
                    consumed = consumed.split("|")
                    consumed = [MS_TILE_2_MJAI_TILE[c] for c in consumed]
                    consumed.sort()
                    if consumed == mjai_consumed:
                        data["data"]["index"] = idx
                        break
                assert data["data"]["index"] != -1
            case "pon":
                data["method"] = ".lq.FastTest.inputChiPengGang"
                data["data"]["type"] = Operation.Peng
                data["data"]["index"] = -1
                data["data"]["timeuse"] = 4

                operation = next(
                    item
                    for item in self.operation["operationList"]
                    if item["type"] == Operation.Peng
                )
                mjai_consumed = mjai_msg["consumed"]
                mjai_consumed.sort()
                for idx, consumed in enumerate(operation["combination"]):
                    consumed = consumed.split("|")
                    consumed = [MS_TILE_2_MJAI_TILE[c] for c in consumed]
                    consumed.sort()
                    if consumed == mjai_consumed:
                        data["data"]["index"] = idx
                        break
                assert data["data"]["index"] != -1
            case "daiminkan":
                data["method"] = ".lq.FastTest.inputChiPengGang"
                data["data"]["type"] = Operation.MingGang
                data["data"]["index"] = -1
                data["data"]["timeuse"] = 4

                operation = next(
                    item
                    for item in self.operation["operationList"]
                    if item["type"] == Operation.MingGang
                )
                mjai_consumed = mjai_msg["consumed"]
                mjai_consumed.sort()
                for idx, consumed in enumerate(operation["combination"]):
                    consumed = consumed.split("|")
                    consumed = [MS_TILE_2_MJAI_TILE[c] for c in consumed]
                    consumed.sort()
                    if consumed == mjai_consumed:
                        data["data"]["index"] = idx
                        break
                assert data["data"]["index"] != -1
            case "ankan":
                data["method"] = ".lq.FastTest.inputOperation"
                data["data"]["type"] = Operation.AnGang
                data["data"]["index"] = -1
                data["data"]["timeuse"] = 4

                operation = next(
                    item
                    for item in self.operation["operationList"]
                    if item["type"] == Operation.MingGang
                )
                mjai_consumed = mjai_msg["consumed"]
                mjai_consumed.sort()
                for idx, consumed in enumerate(operation["combination"]):
                    consumed = consumed.split("|")
                    consumed = [MS_TILE_2_MJAI_TILE[c] for c in consumed]
                    consumed.sort()
                    if consumed == mjai_consumed:
                        data["data"]["index"] = idx
                        break
                assert data["data"]["index"] != -1
            case "kakan":
                data["method"] = ".lq.FastTest.inputOperation"
                data["data"]["type"] = Operation.JiaGang
                data["data"]["index"] = -1
                data["data"]["timeuse"] = 4

                operation = next(
                    item
                    for item in self.operation["operationList"]
                    if item["type"] == Operation.JiaGang
                )
                mjai_consumed = mjai_msg["consumed"] + [mjai_msg["pai"]]
                mjai_consumed.sort()
                for idx, consumed in enumerate(operation["combination"]):
                    consumed = consumed.split("|")
                    consumed = [MS_TILE_2_MJAI_TILE[c] for c in consumed]
                    consumed.sort()
                    if consumed == mjai_consumed:
                        data["data"]["index"] = idx
                        break
                assert data["data"]["index"] != -1
            case "hora":
                if mjai_msg["actor"] == mjai_msg["target"]:
                    data["method"] = ".lq.FastTest.inputOperation"
                    data["data"]["type"] = Operation.Zimo
                else:
                    data["method"] = ".lq.FastTest.inputChiPengGang"
                    data["data"]["type"] = Operation.Hu
                data["data"]["timeuse"] = 4
            case "ryukyoku":
                data["method"] = ".lq.FastTest.inputOperation"
                data["data"]["type"] = Operation.LiuJu
                data["data"]["timeuse"] = 4
            case _:
                raise
        if self.AllReady and len(self.temp) == 0:
            return liqi.compose(data)
        elif self.AllReady:
            temp = self.temp
            self.temp = {}
            return liqi.compose(temp)
        else:
            self.temp = data

    def to_reading(self, mjai_msg):
        pass


def compare_pai(pai1: str, pai2: str):
    # Smallest
    # 1m~4m, 5mr, 5m~9m,
    # 1p~4p, 5pr, 5p~9p,
    # 1s~4s, 5sr, 5s~9s,
    # E, S, W, N, P, F, C, ?
    # Biggest
    pai_order = [
        "1m",
        "2m",
        "3m",
        "4m",
        "5mr",
        "5m",
        "6m",
        "7m",
        "8m",
        "9m",
        "1p",
        "2p",
        "3p",
        "4p",
        "5pr",
        "5p",
        "6p",
        "7p",
        "8p",
        "9p",
        "1s",
        "2s",
        "3s",
        "4s",
        "5sr",
        "5s",
        "6s",
        "7s",
        "8s",
        "9s",
        "E",
        "S",
        "W",
        "N",
        "P",
        "F",
        "C",
        "?",
    ]
    idx1 = pai_order.index(pai1)
    idx2 = pai_order.index(pai2)
    if idx1 > idx2:
        return 1
    elif idx1 == idx2:
        return 0
    else:
        return -1


def meta_to_recommend(meta: dict, is_3p=False) -> dict:
    # """
    # {
    #     "q_values":[
    #         -9.09196,
    #         -9.46696,
    #         -8.365397,
    #         -8.849772,
    #         -9.43571,
    #         -10.06071,
    #         -9.295085,
    #         -0.73649096,
    #         -9.27946,
    #         -9.357585,
    #         0.3221028,
    #         -2.7794597
    #     ],
    #     "mask_bits":2697207348,
    #     "is_greedy":true,
    #     "eval_time_ns":357088300
    # }
    # """

    recommend = []

    mask_unicode_4p = [
        "1万",
        "2万",
        "3万",
        "4万",
        "5万",
        "6万",
        "7万",
        "8万",
        "9万",
        "1饼",
        "2饼",
        "3饼",
        "4饼",
        "5饼",
        "6饼",
        "7饼",
        "8饼",
        "9饼",
        "1索",
        "2索",
        "3索",
        "4索",
        "5索",
        "6索",
        "7索",
        "8索",
        "9索",
        "东",
        "南",
        "西",
        "北",
        "白",
        "发",
        "中",
        "红5万",
        "红5饼",
        "红5索",
        "立直",
        "吃-前",
        "吃-中",
        "吃-后",
        "碰",
        "杠",
        "荣和",
        "流局",
        "无",
    ]

    mask_unicode_3p = [
        "1万",
        "2万",
        "3万",
        "4万",
        "5万",
        "6万",
        "7万",
        "8万",
        "9万",
        "1饼",
        "2饼",
        "3饼",
        "4饼",
        "5饼",
        "6饼",
        "7饼",
        "8饼",
        "9饼",
        "1索",
        "2索",
        "3索",
        "4索",
        "5索",
        "6索",
        "7索",
        "8索",
        "9索",
        "东",
        "南",
        "西",
        "北",
        "白",
        "发",
        "中",
        "红5万",
        "红5饼",
        "红5索",
        "立直",
        "碰",
        "杠",
        "拔北",
        "荣和",
        "流局",
        "无",
    ]
    if is_3p:
        mask_unicode = mask_unicode_3p
    else:
        mask_unicode = mask_unicode_4p

    def mask_bits_to_binary_string(mask_bits):
        binary_string = bin(mask_bits)[2:]
        binary_string = binary_string.zfill(46)
        return binary_string

    def mask_bits_to_bool_list(mask_bits):
        binary_string = mask_bits_to_binary_string(mask_bits)
        bool_list = []
        for bit in binary_string[::-1]:
            bool_list.append(bit == "1")
        return bool_list

    def eq(l, r):
        # Check for approximate equality using numpy's floating-point epsilon
        return np.abs(l - r) <= np.finfo(float).eps

    def softmax(arr, temperature=1.0):
        arr = np.array(arr, dtype=float)  # Ensure the input is a numpy array of floats

        if arr.size == 0:
            return arr  # Return the empty array if input is empty

        if not eq(temperature, 1.0):
            arr /= temperature  # Scale by temperature if temperature is not approximately 1

        # Shift values by max for numerical stability
        max_val = np.max(arr)
        arr = arr - max_val

        # Apply the softmax transformation
        exp_arr = np.exp(arr)
        sum_exp = np.sum(exp_arr)

        softmax_arr = exp_arr / sum_exp

        return softmax_arr

    def scale_list(list):
        scaled_list = softmax(list)
        return scaled_list

    q_values = meta["q_values"]
    mask_bits = meta["mask_bits"]
    mask = mask_bits_to_bool_list(mask_bits)
    scaled_q_values = scale_list(q_values)
    q_value_idx = 0

    true_count = 0
    for i in range(46):
        if mask[i]:
            true_count += 1

    for i in range(46):
        if mask[i]:
            recommend.append((mask_unicode[i], scaled_q_values[q_value_idx]))
            q_value_idx += 1

    recommend = sorted(recommend, key=lambda x: x[1], reverse=True)
    if not recommend:
        return None

    ret = ""
    for i in range(min(len(recommend), 4)):
        ret += f"{recommend[i][0]}: {recommend[i][1]:.2%}\t"

    return ret
