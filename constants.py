import arcade as _arcade

VK_MOVE_UP    = (False, _arcade.key.W)
VK_MOVE_DOWN  = (False, _arcade.key.S)
VK_MOVE_LEFT  = (False, _arcade.key.A)
VK_MOVE_RIGHT = (False, _arcade.key.D)
VK_PATHFINDER = (False, _arcade.key.H)

VK_UNDO_FRAME = (False, _arcade.key.Z)
VK_REDO_FRAME = (False, _arcade.key.X)

VK_PASTE = (True, _arcade.key.V)

VK_INCR_FRATE = (False, _arcade.key.PERIOD)
VK_DECR_FRATE = (False, _arcade.key.COMMA)

VK_SUBMIT_SIM = (False, _arcade.key.B)
VK_TOGGLE_SIM = (False, _arcade.key.K)

VK_SHOW_MENU = (False, _arcade.key.M)

VK_CENTER_CAMERA = (False, _arcade.key.C)

VK_IPDB = (False, _arcade.key.I)
VK_ITEM_TRACER = (False, _arcade.key.L)

VK_CONSOLE = (False, _arcade.key.GRAVE)

VK_SOUL_GRENADE = (True, _arcade.key.T)
VK_FINISHED_MAPS_TRACER = (True, _arcade.key.F)

VK_DOUBLE_SHOOT = (False, _arcade.key.V)

# !!! This needs to be changed every game because we don't know what keys are where yet
ITEMS_TO_MAP = {
    "key_violet" : "cctv",
    "key_purple" : "water",
    "key_orange" : "rusty",
    "key_blue" : "space",
    "goggles" : "logic",
    "boots" : "speed",
    "flag_llm" : "llm",
}
