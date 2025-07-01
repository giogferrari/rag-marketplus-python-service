from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ItemData:
    icon: str
    collection: str
    description: str

@dataclass
class Item:
    nameid: int
    name: str
    jname: str
    value_buy: int
    value_sell: int
    type_: int
    subtype: int
    sex: int
    equip: int
    weight: int
    atk: int
    def_: int  # "def" é palavra reservada
    range_: int
    slot: int
    view_sprite: int
    elv: int
    wlv: int
    view_id: int
    matk: int
    elvmax: int
    delay: int
    flag_trade: int
    flag_refine: int
    flag_buystore: int
    id: int
    account_id: int
    char_id: int
    char_name: str
    shop_name: str
    mapname: str
    map_x: int
    map_y: int
    job: int
    clone_id: int
    idx: int
    price: int
    identify: int
    refine: int
    attribute: int
    unique_id: int
    bonus_time: int
    data: ItemData
    opts: List[str] = field(default_factory=list)
    cards: List[str] = field(default_factory=list)
    cards_sulfix: List[str] = field(default_factory=list)
    amount: int = 1
    is_sub: bool = False
