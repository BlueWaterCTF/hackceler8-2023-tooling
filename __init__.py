import copy
import random
import time
import math
from collections import deque
from dataclasses import dataclass
from typing import Optional, TypeVar

import arcade
import ipdb
import logging

import pyglet.math
import pyperclip

from hack.path_finding import navigate, get_player_coord_from_state
import hack.constants as vk
import hack.hack_util as hack_util

import constants
import json

constants.FONT_NAME = "Arial"

Properties = tuple[tuple[str, any]]
T = TypeVar("T")
BackupOrNone = Optional[tuple[T, any]]

import engine.hitbox


def smart_dup(value) -> any:
    if isinstance(value, (
        list,
        set,
        deque,
    )):
        return value.__class__(smart_dup(v) for v in value)
    if isinstance(value, dict):
        return {k: smart_dup(v) for k, v in value.items()}
    if isinstance(value, (
            engine.hitbox.Point,
    )):
        return copy.deepcopy(value)
    return value


def generic_backup(obj: object, ignore_attrs=()) -> Properties:
    return Properties(
        (key, smart_dup(value))
        for key, value in obj.__dict__.items()
        if key not in ignore_attrs
    )


def generic_restore(obj: T, state: Properties):
    for key, value in state:
        obj.__dict__[key] = value
    return obj


def backup_or_none(obj: T) -> BackupOrNone:
    if obj is None:
        return None
    return obj, obj.backup()


def restore_or_none(backup: BackupOrNone) -> T:
    if backup is None:
        return None
    obj, state = backup
    obj.restore(state)
    return obj


def inject_class(cls, hacked_cls):
    for subclass in cls.__subclasses__():
        if subclass is not hacked_cls:
            subclass.__bases__ = (hacked_cls,)


import hashlib

def string_to_color(s: str) -> tuple:
    hash_object = hashlib.md5(s.encode())
    hashed = hash_object.hexdigest()

    r = int(hashed[:2], 16)
    g = int(hashed[2:4], 16)
    b = int(hashed[4:6], 16)

    blend_factor = 0.4
    r = int(r + (255 - r) * blend_factor)
    g = int(g + (255 - g) * blend_factor)
    b = int(b + (255 - b) * blend_factor)

    return (r, g, b)


# engine/rng.py
import engine.rng


@dataclass(frozen=True, kw_only=True)
class RngSystemBackupState:
    random_state: tuple
    frng_state: tuple
    prng_state: tuple


class HackedRngSystem(engine.rng.RngSystem):
    def backup(self) -> RngSystemBackupState:
        return RngSystemBackupState(
            random_state=random.getstate(),
            frng_state=self.frng.getstate(),
            prng_state=self.prng.getstate(),
        )

    def restore(self, state: RngSystemBackupState):
        random.setstate(state.random_state)
        self.frng.setstate(state.frng_state)
        self.prng.setstate(state.prng_state)

    # disable copy/deepcopy
    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


inject_class(engine.rng.RngSystem, HackedRngSystem)
engine.rng.RngSystem = HackedRngSystem

# engine/walk_data.py
import engine.walk_data

@dataclass(frozen=True, kw_only=True)
class WalkDataBackupState:
    properties: Properties
    rng: tuple


class HackedWalkData(engine.walk_data.WalkData):
    def backup(self) -> WalkDataBackupState:
        return WalkDataBackupState(
            properties=generic_backup(self, ignore_attrs=('obj',)),
            rng=self.rng.getstate() if self.rng else None,
        )
        return generic_backup(self, ('obj',))

    def restore(self, state: Properties):
        generic_restore(self, state.properties)

        if state.rng:
            self.rng.setstate(state.rng)
        else:
            self.rng = None

    # disable copy/deepcopy
    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


inject_class(engine.walk_data.WalkData, HackedWalkData)
engine.walk_data.WalkData = HackedWalkData

# engine/generics.py
import engine.generics


@dataclass(frozen=True, kw_only=True)
class GenericObjectBackupState:
    properties: Properties
    walk_data: BackupOrNone
    hashable_outline: tuple


class FakeHashableOutline(set):
    string = None

    def __str__(self):
        assert self.string is not None
        return self.string


G_GenericObjectTracerLabelOutlines = dict()
G_GenericObjectTracerLabels = dict()
G_GenericObjectTitleLabels = dict()

class HackedGenericObject(engine.generics.GenericObject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game = None

    def __del__(self):
        G_GenericObjectTracerLabelOutlines.pop(id(self), None)
        G_GenericObjectTracerLabels.pop(id(self), None)
        G_GenericObjectTitleLabels.pop(id(self), None)

    def backup(self) -> GenericObjectBackupState:
        return GenericObjectBackupState(
            properties=generic_backup(self, ignore_attrs=('game', 'hashable_outline')),
            walk_data=backup_or_none(self.walk_data),
            hashable_outline=copy.deepcopy(self.hashable_outline),
        )

    def restore(self, state: GenericObjectBackupState):
        generic_restore(self, state.properties)
        self.walk_data = restore_or_none(state.walk_data)
        self.hashable_outline = state.hashable_outline

    def _has_health(self):
        # NOTE: only Enemys, Players, and destroyable weapons can take damage
        # from projectiles. (This is because when CombatSystem is initialized it
        # is passed with only the targets including the set of Enemy objects
        match self.nametype:
            case 'Enemy':
                has_health = True
            case 'Player':
                has_health = True
            case 'Weapon':
                has_health = self.destroyable
            case _:
                has_health = False
        return has_health

    def draw(self):
        super().draw()
        self._draw()

        has_drawn_title = False
        # Draw a line and label to each object
        draw_label_blocklist = ["Player", "Spike"]
        if hasattr(self, 'game') and self.game and self.game.item_tracer and not self.nametype in draw_label_blocklist:
            dx = self.x - self.game.player.x
            dy = self.y - self.game.player.y

            distance_to_object = (dx**2 + dy**2)**0.5
            adjusted_dx = dx / distance_to_object if distance_to_object else 0
            adjusted_dy = dy / distance_to_object if distance_to_object else 0

            label_distance = 400
            if distance_to_object < label_distance:
                label_distance = distance_to_object // 2

            label_x = self.game.player.x + adjusted_dx * label_distance
            label_y = self.game.player.y + adjusted_dy * label_distance

            text_color = string_to_color(self.nametype)

            arcade.draw_line(self.game.player.x, self.game.player.y, self.x, self.y, text_color)

            if (abs(dx / self.game.gui.camera.scale) >= self.game.gui.camera.viewport_width // 2) or \
                (abs(dy / self.game.gui.camera.scale) >= self.game.gui.camera.viewport_height // 2):
                if not id(self) in G_GenericObjectTracerLabelOutlines:
                    G_GenericObjectTracerLabelOutlines[id(self)] = arcade.Text(self.name or self.nametype or '', 0, 0, arcade.color.BLACK, 11)
                    G_GenericObjectTracerLabels[id(self)] = arcade.Text(self.name or self.nametype or '', 0, 0, text_color, 11)
                G_GenericObjectTracerLabels[id(self)].x = label_x
                G_GenericObjectTracerLabels[id(self)].y = label_y
                G_GenericObjectTracerLabelOutlines[id(self)].x = label_x + 1
                G_GenericObjectTracerLabelOutlines[id(self)].y = label_y - 1
                G_GenericObjectTracerLabelOutlines[id(self)].draw()
                G_GenericObjectTracerLabels[id(self)].draw()

            r = self.get_rect()
            if not id(self) in G_GenericObjectTitleLabels:
                G_GenericObjectTitleLabels[id(self)] = arcade.Text(self.name or self.nametype, 0, 0, text_color, 11, anchor_x='center', anchor_y='baseline',)
            G_GenericObjectTitleLabels[id(self)].x = (r.x1() + r.x2()) // 2
            G_GenericObjectTitleLabels[id(self)].y = r.y2() + 5
            G_GenericObjectTitleLabels[id(self)].draw()
            has_drawn_title = True

        # Draw soul grenade trajectory
        if hasattr(self, "game") and self.game is not None and self.game.soul_tracer and self.game.current_mode.value == "platformer":
            rad = abs((self.game.tics % constants.SWING_TICKS) / constants.SWING_TICKS * 2 - 1) * 0.5 * math.pi
            cosrad = math.cos(rad)
            sinrad = math.sin(rad)
            x_speed, y_speed = cosrad * constants.SOUL_SPEED, sinrad * constants.SOUL_SPEED

            player_w = self.game.player.get_width()
            player_h = self.game.player.get_height()

            offset = (player_w ** 2 + player_h ** 2) ** 0.5 // 2 + 20
            offset_x, offset_y = cosrad * offset, sinrad * offset
            if self.game.player.face_towards == "W":
                offset_x = -offset_x
                x_speed = -x_speed

            offset_x += self.game.player.x + 10
            offset_y += self.game.player.y + 10
            arcade.draw_line(self.game.player.x, self.game.player.y, offset_x, offset_y, arcade.color.YELLOW)

        # Draw line of sight for enemies
        if self.nametype == 'Enemy':
            if self.one_sided:
                if self.sprite.flipped:
                    start_angle = 90.0
                    end_angle = 270.0
                else:
                    start_angle = -90.0
                    end_angle = 90.0
            else:
                    start_angle = 0.0
                    end_angle = 360.0
            arcade.draw_arc_outline(self.x, self.y, self.sight * 2, self.sight * 2,
                    arcade.color.GREEN, start_angle, end_angle)
            arcade.draw_arc_filled(self.x, self.y, self.sight * 2, self.sight * 2,
                    (0, 255, 0, 20), start_angle, end_angle)

        # Draw healthbar
        if self._has_health():
            bar_width = self.max_health
            bar_height = 10
            bar_padding = 20 if has_drawn_title else 5
            arcade.draw_xywh_rectangle_outline(self.get_leftmost_point() - bar_width // 2 + self.get_width() // 2,
                    self.get_highest_point() + bar_padding, bar_width, bar_height, arcade.color.GREEN)
            arcade.draw_xywh_rectangle_filled(self.get_leftmost_point() - bar_width // 2 + self.get_width() // 2,
                    self.get_highest_point() + bar_padding, self.health, bar_height, arcade.color.GREEN)

    @property
    def hashable_outline(self):
        return self.__dict__['hashable_outline']

    @hashable_outline.setter
    def hashable_outline(self, value):
        if value is None:
            self.__dict__['hashable_outline'] = None
            return
        fake = FakeHashableOutline(value)
        fake.string = str(value)
        self.__dict__['hashable_outline'] = fake

    # disable copy/deepcopy
    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


inject_class(engine.generics.GenericObject, HackedGenericObject)
engine.generics.GenericObject = HackedGenericObject


# components/enemy/enemy.py
import components.enemy.enemy

components.enemy.enemy.Enemy.sight = 400
components.enemy.enemy.Enemy.one_sided = True

components.enemy.enemy.StaticJellyfish.sight = 70 # This is the stinging radius
components.enemy.enemy.StaticJellyfish.one_sided = False

# components/player.py
import components.player
components.player.Player.max_health = 100

# components/weapon_systems/base.py
import components.weapon_systems.base
import components.logic


class HackedWeapon(components.weapon_systems.base.Weapon):
    max_health = 100
    # allow copy/deepcopy for Weapon
    # __copy__ = None
    __deepcopy__ = None


inject_class(components.weapon_systems.base.Weapon, HackedWeapon)
components.weapon_systems.base.Weapon = HackedWeapon

# components/danmaku.py
import components.danmaku


class FakeBulletIterator:
    def __init__(self, bullet_obj, updater):
        self.bullet_obj = bullet_obj
        self.updater = updater
        self.state = None
        self.next = None

    def __next__(self):
        if self.next is not None:
            if self.next.state is None:
                self.bullet_obj.kill()
            else:
                generic_restore(self.bullet_obj, self.next.state)
            return
        next(self.updater)
        if self.bullet_obj.fake_iterator is self:  # the updater might change the iterator as well...
            self.bullet_obj.fake_iterator = FakeBulletIterator(self.bullet_obj, self.updater)
        self.next = self.bullet_obj.fake_iterator
        self.updater = None


class HackedBullet(components.danmaku.Bullet):
    fake_iterator = None

    @property
    def updater(self):
        return self.fake_iterator

    @updater.setter
    def updater(self, value):
        self.fake_iterator = FakeBulletIterator(self, value)

    def backup(self):
        state = generic_backup(self)
        self.fake_iterator.state = state
        return state

    # disable copy/deepcopy
    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


inject_class(components.danmaku.Bullet, HackedBullet)
components.danmaku.Bullet = HackedBullet

# map_loading/tilemap.py
import map_loading.tilemap


@dataclass(frozen=True, kw_only=True)
class BasicTileMapBackupState:
    properties: Properties
    moving_platforms: tuple


class HackedBasicTileMap(map_loading.tilemap.BasicTileMap):
    def backup(self) -> BasicTileMapBackupState:
        return BasicTileMapBackupState(
            properties=generic_backup(self, ('moving_platforms','texts','layers','static_objs','parsed_map', 'map_size')),
            moving_platforms=tuple(
                (platform, platform.backup())
                for platform in self.moving_platforms
            )
        )

    def restore(self, state: BasicTileMapBackupState):
        generic_restore(self, state.properties)
        self.moving_platforms.clear()
        for platform, platform_state in state.moving_platforms:
            platform.restore(platform_state)
            self.moving_platforms.append(platform)

    # disable copy/deepcopy
    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


inject_class(map_loading.tilemap.BasicTileMap, HackedBasicTileMap)
map_loading.tilemap.BasicTileMap = HackedBasicTileMap

# engine/logic.py
import engine.logic


@dataclass(frozen=True, kw_only=True)
class LogicEngineBackupState:
    logic_map: tuple
    logic_countdown: int
    spritelist: tuple


class HackedLogicEngine(engine.logic.LogicEngine):
    def backup(self) -> LogicEngineBackupState:
        return LogicEngineBackupState(
            logic_map=tuple(
                (key, value.backup())
                for key, value in self.logic_map.items()
            ),
            logic_countdown=self.logic_countdown,
            spritelist=tuple((x, generic_backup(x)) for x in self.spritelist)
        )

    def restore(self, state: LogicEngineBackupState):
        self.logic_countdown = state.logic_countdown
        for key, state in state.logic_map:
            self.logic_map[key].restore(state)
        self.spritelist.clear()
        self.spritelist.extend(generic_restore(x, y) for x, y in state.spritelist)

    # disable copy/deepcopy
    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


inject_class(engine.logic.LogicEngine, HackedLogicEngine)
engine.logic.LogicEngine = HackedLogicEngine

# engine/physics.py
import engine.physics


class HackedPhysicsEngine(engine.physics.PhysicsEngine):
    def backup(self) -> Properties:
        return generic_backup(self, ('player',))

    def restore(self, state: Properties):
        generic_restore(self, state)

    # disable copy/deepcopy
    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


inject_class(engine.physics.PhysicsEngine, HackedPhysicsEngine)
engine.physics.PhysicsEngine = HackedPhysicsEngine

# engine/danmaku.py
import engine.danmaku


@dataclass(frozen=True, kw_only=True)
class DanmakuSystemBackupState:
    properties: Properties
    gui: tuple
    bullets: tuple
    player_bullets: tuple


class HackedDanmakuSystem(engine.danmaku.DanmakuSystem):
    def backup(self) -> DanmakuSystemBackupState:
        return DanmakuSystemBackupState(
            properties=generic_backup(self, ignore_attrs=('gui', 'player', 'boss')),
            gui=smart_dup(self.gui),
            bullets=tuple((bullet, bullet.backup()) for bullet in self.bullets),
            player_bullets=tuple((bullet, bullet.backup()) for bullet in self.player_bullets),
        )

    def restore(self, state: DanmakuSystemBackupState):
        self.bullets.clear(deep=False)
        self.player_bullets.clear(deep=False)
        generic_restore(self, state.properties)
        self.gui = dict(state.gui)
        self.bullets.extend(generic_restore(bullet, state) for bullet, state in state.bullets)
        self.player_bullets.extend(generic_restore(bullet, state) for bullet, state in state.player_bullets)

    def draw(self):
        super().draw()
        self._draw()

    # disable copy/deepcopy
    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


inject_class(engine.danmaku.DanmakuSystem, HackedDanmakuSystem)
engine.danmaku.DanmakuSystem = HackedDanmakuSystem

# components/portal.py
import components.portal
OriginalPortal = components.portal.Portal
class HackedPortal(components.portal.Portal):
    def draw(self):
        super().draw()
        # The Portal object is missing the super call so we manually patch it here
        super(OriginalPortal, self).draw()

inject_class(components.portal.Portal, HackedPortal)
components.portal.Portal = HackedPortal

# engine/grenade.py
import engine.grenade


@dataclass(frozen=True, kw_only=True)
class GrenadeSystemBackupState:
    properties: Properties
    grenades: tuple


class HackedGrenadeSystem(engine.grenade.GrenadeSystem):
    def backup(self) -> GrenadeSystemBackupState:
        return GrenadeSystemBackupState(
            properties=generic_backup(self, ('game',)),
            grenades=tuple(grenade.backup() for grenade in self.grenades),
        )

    def restore(self, state: GrenadeSystemBackupState):
        generic_restore(self, state.properties)
        for grenade, grenade_state in zip(self.grenades, state.grenades):
            grenade.restore(grenade_state)

    # disable copy/deepcopy
    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


inject_class(engine.grenade.GrenadeSystem, HackedGrenadeSystem)
engine.grenade.GrenadeSystem = HackedGrenadeSystem

# engine/map_switcher.py
import engine.map_switcher

# engine/combat.py
import engine.combat


@dataclass(frozen=True, kw_only=True)
class CombatSystemBackupState:
    properties: Properties
    active_projectiles: tuple


class HackedCombatSystem(engine.combat.CombatSystem):
    def backup(self) -> CombatSystemBackupState:
        return CombatSystemBackupState(
            properties=generic_backup(self, ('game', 'active_projectiles')),
            active_projectiles=tuple((projectile, projectile.backup()) for projectile in self.active_projectiles),
        )

    def restore(self, state: CombatSystemBackupState):
        generic_restore(self, state.properties)
        self.active_projectiles.clear()
        for projectile, projectile_state in state.active_projectiles:
            projectile.restore(projectile_state)
            self.active_projectiles.append(projectile)

    # disable copy/deepcopy
    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


inject_class(engine.combat.CombatSystem, HackedCombatSystem)
engine.combat.CombatSystem = HackedCombatSystem

# components/textbox.py
import components.textbox

# ludicer.py
import ludicer


@dataclass(frozen=True, kw_only=True)
class LudicerBackupState:
    properties: Properties
    map_switch: engine.map_switcher.MapSwitch
    objects: tuple[GenericObjectBackupState]
    items: tuple
    textbox: components.textbox.Textbox
    rng_system: RngSystemBackupState
    player: BackupOrNone
    tiled_map: BackupOrNone
    combat_system: BackupOrNone
    physics_engine: BackupOrNone
    logic_engine: BackupOrNone
    danmaku_system: BackupOrNone
    grenade_system: BackupOrNone
    brainduck: BackupOrNone
    boss: any
    sent_game_info: dict


class FakeNet:
    def __init__(self):
        self.msg = None

    def send_one(self, msg):
        self.msg = msg


class HackedLudicer(ludicer.Ludicer):
    objects: tuple[HackedGenericObject]
    __last_sent = None
    inverted_controls = False
    real_time = True
    simulating = False
    item_tracer = False
    soul_tracer = False
    finished_maps_tracer = False

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self._move_keys = set()


    def backup(self) -> LudicerBackupState:
        return LudicerBackupState(
            properties=tuple(
                (key, getattr(self, key))
                for key in (
                    'tics',
                    'player_last_base_position',
                    'current_map',
                    'scene',
                    'prerender',
                    'current_mode',
                    'state_hash',
                    'cheating_detected',
                    'win_timestamp',
                    'prev_display_inventory',
                    'display_inventory',
                    'save_cooldown',
                    'save_cooldown_timer',
                    'rand_seed',
                )
            ) + tuple(
                (key, copy.copy(getattr(self, key)))
                for key in (
                    'unlocked_doors',
                    'newly_pressed_keys',
                    'prev_pressed_keys',
                    'pressed_keys',
                    'objects',
                    'static_objs',
                )
            ),
            map_switch=copy.copy(self.map_switch),
            objects=tuple(o.backup() for o in self.objects),
            items=tuple(self.items),
            tiled_map=backup_or_none(self.tiled_map),
            textbox=copy.copy(self.textbox),
            rng_system=self.rng_system.backup(),
            player=backup_or_none(self.player),
            combat_system=backup_or_none(self.combat_system),
            physics_engine=backup_or_none(self.physics_engine),
            logic_engine=backup_or_none(self.logic_engine),
            danmaku_system=backup_or_none(self.danmaku_system),
            grenade_system=backup_or_none(self.grenade_system),
            brainduck=backup_or_none(self.brainduck),
            boss=self.boss,
            sent_game_info=self.__last_sent,
        )

    def dump_items(self, *args, **kwargs):
        _G_WINDOW.console_add_msg('save_state written')
        super().dump_items(*args, **kwargs)

    def restore(self, state: LudicerBackupState):
        generic_restore(self, state.properties)

        for o, s in zip(self.objects, state.objects):
            o.restore(s)
        self.boss = state.boss
        self.items = list(state.items)

        self.rng_system.restore(state.rng_system)

        self.map_switch = state.map_switch
        self.textbox = state.textbox

        self.tiled_map = restore_or_none(state.tiled_map)
        self.player = restore_or_none(state.player)
        self.combat_system = restore_or_none(state.combat_system)
        self.physics_engine = restore_or_none(state.physics_engine)
        self.logic_engine = restore_or_none(state.logic_engine)
        self.danmaku_system = restore_or_none(state.danmaku_system)
        self.grenade_system = restore_or_none(state.grenade_system)
        self.brainduck = restore_or_none(state.brainduck)

        self.__last_sent = None

    def setup(self):
        super().setup()
        # For some reason the game is not set for the weapons,
        # unlike other objects so we need to manually set them here so
        # we can draw the traces from the player
        for o in list(self.combat_system.weapons):
            o.game = self

        # The `generic_platform` are walls, which are too many.
        # The `zone`s are not interesting so skipping it too.
        for o in list(self.static_objs):
            if o.name != "generic_platform" and not "zone" in o.name:
                o.game = self

    def send_game_info(self):
        if self.real_time and not self.simulating:
            super().send_game_info()
        else:
            net = self.net
            self.net = FakeNet()
            super().send_game_info()
            self.__last_sent = self.net.msg
            self.net = net

    @property
    def raw_pressed_keys(self):
        raw_pressed_keys = self.__dict__['raw_pressed_keys']
        if not self.simulating and self.inverted_controls:
            raw_pressed_keys = raw_pressed_keys.copy()

            inverted_sets = [
                (vk.VK_MOVE_UP, vk.VK_MOVE_DOWN[1]),
                (vk.VK_MOVE_DOWN, vk.VK_MOVE_UP[1]),
                (vk.VK_MOVE_LEFT, vk.VK_MOVE_RIGHT[1]),
                (vk.VK_MOVE_RIGHT, vk.VK_MOVE_LEFT[1]),
            ]
            for (_, k) in inverted_sets:
                if k in raw_pressed_keys:
                    raw_pressed_keys.remove(k)
            for (k1, k2) in inverted_sets:
                if k1 in self._move_keys:
                    raw_pressed_keys.add(k2)
        return frozenset(raw_pressed_keys)

    @raw_pressed_keys.setter
    def raw_pressed_keys(self, value):
        self.__dict__['raw_pressed_keys'] = value

    def __copy__(self):
        raise NotImplementedError

    def __deepcopy__(self, _):
        raise NotImplementedError


ludicer.Ludicer = HackedLudicer

# ludicer_gui.py
import ludicer_gui

ludicer_gui.SCREEN_TITLE += " [Blue Water 💦​]"

REFRESH_RATE_DELTA = (120 - 60) / 10

SPEED_DIAL = [.1, .2, .5, 1.0, 1.5, 2.0, 4.0, 10.0]
def get_update_rate(ind):
    ind = max(0, min(len(SPEED_DIAL) - 1, ind))
    speed = SPEED_DIAL[ind]
    return 1 / (60 * speed)

global _G_WINDOW

class HackedHackceler8(ludicer_gui.Hackceler8):
    game: HackedLudicer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__history = []
        self.__history_index = -1  # location of the current state in history
        self.__speed_dial = 4
        self.__key_pressed = set()
        self.__mouse = (0, 0)
        self.__free_camera = False
        self.__last_path_find = []
        # self.on_click_start(None)

        self.__console = False
        self.__console_cmd_buf = ''
        self.__console_msgs = []
        self.__console_commands = {
            'help': self.cmd_help,
            'dumplogic': self.cmd_logic,
            'dumpsim': self.cmd_dumpsim,
            'loadsim': self.cmd_loadsim
        }
        self.__last_map_visited = None
        self.__last_map_objects_count = 0
        self.__last_map_major_info = None


        # silly :-)
        global _G_WINDOW
        _G_WINDOW = self

    def start_game(self):
        super().start_game()
        self.game.gui = self

    def append_history(self, state):
        self.__history_index += 1
        self.__history = self.__history[:self.__history_index]
        self.__history.append(state)

    def restore_history(self, forward):
        if forward:
            if self.__history_index + 1 >= len(self.__history):
                return
            self.__history_index += 1
        else:
            if self.__history_index <= 0:
                return
            self.__history_index -= 1

        if self.__history[self.__history_index] is None:
            # seek
            self.__history_index += 1 if forward else -1
            while 0 <= self.__history_index < len(self.__history):
                state = self.__history[self.__history_index]
                self.__history_index += 1 if forward else -1
                if state is None:
                    break
            else:
                raise RuntimeError('seek failed')

        if 0 <= self.__history_index < len(self.__history):
            self.game.restore(self.__history[self.__history_index])

    def sim_should_run(self):
        return self.game is not None and len(self.game.raw_pressed_keys) > 0

    def window_to_game_coord(self, x, y):
        half_width = self.camera.viewport_width / 2
        half_height = self.camera.viewport_height / 2
        actual_x = (x - half_width) * self.camera.scale + half_width + self.camera.goal_position.x
        actual_y = (y - half_height) * self.camera.scale + half_height + self.camera.goal_position.y
        return actual_x, actual_y

    def game_to_window_coord(self, x, y):
        half_width = self.camera.viewport_width / 2
        half_height = self.camera.viewport_height / 2
        actual_x = (x - self.camera.goal_position.x - half_width) / self.camera.scale + half_width
        actual_y = (y - self.camera.goal_position.y - half_height) / self.camera.scale + half_height
        return actual_x, actual_y

    def extra_draw(self):
        if self.game.real_time:
            text = 'REALTIME'
        else:
            text = f'SIM ({self.__history_index + 1}/{len(self.__history)}) '
            if vk.VK_UNDO_FRAME[1] in self.__key_pressed and self.__history_index > 0:
                text += 'UNDOING'
            elif vk.VK_REDO_FRAME[1] in self.__key_pressed and self.__history_index < len(self.__history) - 1:
                text += 'REDOING'
            elif self.sim_should_run():
                text += 'RUNNING'
            else:
                text += 'PAUSED'

        if self.game and self.game.finished_maps_tracer:
            for item in self.game.global_match_items.items:
                if item.collected_time > 0 and item.name in vk.ITEMS_TO_MAP:
                    item_map = vk.ITEMS_TO_MAP[item.name]
                    arena_name = None
                    for k, v in self.game.arena_mapping.items():
                        if v == item_map:
                            arena_name = k
                    if arena_name:
                        for o in self.game.static_objs:
                            if o.name == arena_name:
                                p0x, p0y = self.game_to_window_coord(o.perimeter[0].x, o.perimeter[0].y)
                                p1x, p1y = self.game_to_window_coord(o.perimeter[1].x, o.perimeter[1].y)
                                p2x, p2y = self.game_to_window_coord(o.perimeter[2].x, o.perimeter[2].y)
                                arcade.draw_lrtb_rectangle_filled(p0x, p1x, p0y, p2y, arcade.color.RED)

        arcade.draw_text(
            text + ' (%.1fx)' % (SPEED_DIAL[self.__speed_dial]),
            self.camera.viewport_width,
            0,
            arcade.csscolor.WHITE,
            18,
            anchor_x='right',
            anchor_y='bottom',
            )

        if self.game and self.game.player and self.game.player.get_height() // 2 == 15:
            arcade.draw_text(
                "sticky triggered",
                self.camera.viewport_width / 2,
                self.camera.viewport_height,
                arcade.csscolor.BLUE,
                16,
                anchor_x='center',
                anchor_y='top',
            )

        if self.game:
            if self.__last_map_visited != self.game.current_map and self.__last_map_objects_count != len(self.game.objects):
                self.__last_map_visited = self.game.current_map
                self.__last_map_objects_count = len(self.game.objects)
                text_parts = []
                for o in self.game.objects:
                    if o.nametype == "Item":
                        text_parts.append(o.display_name)
                    elif o.name is not None and "npc" in o.name:
                        text_parts.append(o.name.replace('_', ' ').title())
                self.__last_map_major_info = arcade.Text(
                    '[' + self.game.current_map.title() + "] " + (', ').join(text_parts),
                    self.camera.viewport_width / 2,
                    5,
                    arcade.csscolor.WHITE,
                    20,
                    anchor_x='center',
                    anchor_y='bottom',
                )
            if self.__last_map_visited:
                self.__last_map_major_info.draw()

        x, y = self.window_to_game_coord(*self.__mouse)
        arcade.draw_text(
            f'({x:.1f}, {y:.1f})',
            self.__mouse[0],
            self.__mouse[1],
            arcade.csscolor.WHITE,
            12,
        )

        console_fontsize = 14
        lines = [(l,arcade.csscolor.WHITE) for l in self.__console_msgs[-5:]]
        if self.__console:
            lines.append(('>' + self.__console_cmd_buf, arcade.csscolor.WHITE))
            for cmdname in self.__console_commands:
                if cmdname.startswith(self.__console_cmd_buf):
                    lines.append(('>' + cmdname, arcade.csscolor.DIM_GRAY))
        for i,(line,color) in enumerate(lines):
            arcade.draw_text(
                line,
                1,
                self.camera.viewport_height-i*(console_fontsize*1.15)-1,
                arcade.csscolor.BLACK,
                console_fontsize,
                anchor_x='left',
                anchor_y='top',
            )
            arcade.draw_text(
                line,
                0,
                self.camera.viewport_height-i*(console_fontsize*1.15),
                color,
                console_fontsize,
                anchor_x='left',
                anchor_y='top',
            )

        self.camera.use()
        for x, y in self.__last_path_find:
            arcade.draw_circle_filled(x, y, 1, arcade.csscolor.BLUE)
        if 'visited' in self.game.__dict__:
            for x,y,vx,vy in self.game.visited:
                arcade.draw_circle_filled(x, y, 1, arcade.csscolor.GREEN)
        if self.game.item_tracer:
            for name, elem in self.game.logic_engine.logic_map.items():
                line = name
                if isinstance(elem, components.logic.Toggle):
                    arcade.draw_text(
                        f'val={elem.index}',
                        elem.x,
                        elem.y+14,
                        arcade.csscolor.WHITE,
                        12,
                        anchor_x='left',
                        anchor_y='top'
                    ),
                arcade.draw_text(
                    line,
                    elem.x,
                    elem.y,
                    arcade.csscolor.WHITE,
                    12,
                    anchor_x='left',
                    anchor_y='top'
                )
        self.gui_camera.use()

    def change_refresh_rate(self, delta):
        self.__speed_dial = max(0, min(len(SPEED_DIAL) - 1, self.__speed_dial + delta))
        self.set_update_rate(get_update_rate(self.__speed_dial))

    def actual_tick(self):
        if self.game.player is None:
            return self.game.tick()

        if 0 <= self.__history_index < len(self.__history):
            state = self.__history[self.__history_index]
        else:
            state = self.game.backup()
        self.game.inverted_controls = self.game.player.inverted_controls
        self.game.tick()
        if self.game.inverted_controls != self.game.player.inverted_controls:
            # inverted controls changed, rerun the tick
            self.game.inverted_controls = self.game.player.inverted_controls
            self.game.restore(state)
            self.game.tick()

    def on_update(self, _delta_time: float):
        if self.game is None:
            return

        if self.game.real_time:
            tmp = super().on_update(_delta_time)
            self.game.inverted_controls = self.game.player.inverted_controls
            return tmp

        if vk.VK_UNDO_FRAME[1] in self.__key_pressed:
            self.restore_history(forward=False)

        if vk.VK_REDO_FRAME[1] in self.__key_pressed:
            self.restore_history(forward=True)

        if self.sim_should_run():
            if self.game.map_switch is not None:
                # skip map switch animation
                self.append_history(None)  # seek point A
                while self.game.map_switch is not None:
                    self.game.tick()
                    self.append_history(self.game.backup())
                self.append_history(None)  # seek point B
            self.actual_tick()
            self.append_history(self.game.backup())
        self.center_camera_to_player()

    def submit_info(self):
        if self.__history_index < 0:
            return
        submission = self.__history[:self.__history_index + 1]
        self.__history = self.__history[self.__history_index + 1:]
        self.__history_index = -1
        if not self.game.net:
            return
        for state in submission:
            if state is None:
                continue
            self.game.net.send_one(state.sent_game_info)
        # for _ in range(20):
        #     time.sleep(0.1)
        #     self.game.recv_from_server()
        #     if self.game.cheating_detected:
        #         raise RuntimeError('cheating detected')

    def center_camera_to_player(self):
        if self.__free_camera:
            return

        half_width = self.camera.viewport_width / 2
        half_height = self.camera.viewport_height / 2
        half_width_s = half_width * self.camera.scale
        half_height_s = half_height * self.camera.scale
        camera_x = pyglet.math.clamp(
            self.game.player.x, half_width_s, self.game.tiled_map.map_size_pixels[0] - half_width_s)
        camera_y = pyglet.math.clamp(
            self.game.player.y, half_height_s, self.game.tiled_map.map_size_pixels[1] - half_height_s)
        self.camera.move((camera_x - half_width, camera_y - half_height))

    def on_key_press(self, symbol: int, modifiers: int):
        if not self.__on_key_press_hijack(
            symbol, modifiers
        ):
            if self.game is None:
                return
            if symbol in self.game.tracked_keys:
                self.game.__dict__['raw_pressed_keys'].add(symbol)

    def there_is_a_window(self) -> bool:
        return self.game.textbox is not None

    def __on_key_press_hijack(self, symbol: int, modifiers: int) -> bool:
        hijacked = False
        # There is a bug that when command is pressed on a Mac, the value would be 512 | 64 instead of 64,
        # so we have to use & to check here
        ctrl = modifiers == arcade.key.MOD_CTRL or modifiers & arcade.key.MOD_COMMAND
        logging.debug("Pressed: {symbol}{with_ctrl}".format(
            symbol = symbol,
            with_ctrl = " [CTRL]" if ctrl else "",
        ))
        if self.game is None:
            return False
        if self.__console:
            if symbol == arcade.key.RETURN:
                self.__console = False
                cmd = self.__console_cmd_buf
                self.__console_cmd_buf = ''
                self.on_console_command(cmd)
            elif symbol == arcade.key.BACKSPACE:
                self.__console_cmd_buf = self.__console_cmd_buf[:-1]
            elif 0x20 <= symbol < 0x7f:
                if modifiers & arcade.key.MOD_SHIFT:
                    c = chr(hack_util.shifted_keycode(symbol))
                else:
                    c = chr(symbol)
                self.__console_cmd_buf += c
            return True
        # To avoid some unexpected behaviors, we don't hijack single key press
        # event when there is a GUI window
        if not ctrl and self.there_is_a_window():
            return False

        if (ctrl, symbol) in [vk.VK_MOVE_UP, vk.VK_MOVE_LEFT, vk.VK_MOVE_DOWN,
                vk.VK_MOVE_RIGHT]:
            self.game._move_keys.add((ctrl, symbol))

        match (ctrl, symbol):
            case vk.VK_INCR_FRATE:
                self.change_refresh_rate(1)
                return True
            case vk.VK_DECR_FRATE:
                self.change_refresh_rate(-1)
                return True
            case vk.VK_SUBMIT_SIM:
                self.submit_info()
                return True
            case vk.VK_TOGGLE_SIM:
                if self.game.real_time:
                    self.game.real_time = False
                elif len(self.__history) == 0:
                    self.game.real_time = True
                return True
            case vk.VK_SHOW_MENU:
                logging.info("Showing menu")
                self.show_menu()
                return True
            case vk.VK_CENTER_CAMERA:
                if self.__free_camera:
                    self.__free_camera = False
                else:
                    self.camera.scale = 1
                self.center_camera_to_player()
                return True
            case vk.VK_PATHFINDER:
                if self.game.real_time:
                    return False
                history = navigate(self.game, *self.window_to_game_coord(*self.__mouse))
                if not history:
                    return False
                self.__last_path_find = []
                for h in history:
                    self.__last_path_find.append(get_player_coord_from_state(h))
                    self.append_history(h)
                self.game.restore(self.__history[self.__history_index])
                return True
            case vk.VK_IPDB:
                ipdb.set_trace()
                return True
            case vk.VK_ITEM_TRACER:
                self.game.item_tracer = not self.game.item_tracer
                return True
            case vk.VK_SOUL_GRENADE:
                self.game.soul_tracer = not self.game.soul_tracer
                return True
            case vk.VK_FINISHED_MAPS_TRACER:
                self.game.finished_maps_tracer = not self.game.finished_maps_tracer
                return True
            case vk.VK_PASTE:
                if self.game.textbox.text_input_appeared:
                    self.game.textbox.text_input.text = pyperclip.paste()
                    return True
            case vk.VK_CONSOLE:
                self.__console = True
            case vk.VK_DOUBLE_SHOOT:
                if self.game.real_time:
                    return False
                return True
            case _:
                self.__key_pressed.add(symbol)
                return False
        return False

    def on_key_release(self, symbol: int, modifiers: int):
        self.__key_pressed.discard(symbol)
        ctrl = modifiers == arcade.key.MOD_CTRL or modifiers & arcade.key.MOD_COMMAND
        if self.game is not None:
            if (ctrl, symbol) in self.game._move_keys:
                self.game._move_keys.remove((ctrl, symbol))
            self.game.__dict__['raw_pressed_keys'].discard(symbol)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
        self.__mouse = x, y

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        if buttons != arcade.MOUSE_BUTTON_RIGHT:
            return
        self.__free_camera = True
        if modifiers & arcade.key.MOD_CTRL:
            dx *= 2
            dy *= 2
        self.camera.goal_position.x -= dx * self.camera.scale
        self.camera.goal_position.y -= dy * self.camera.scale

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        diff = scroll_y / 10
        scale = self.camera.scale + diff
        if scale <= 0.1:
            return
        self.camera.scale = scale
        self.center_camera_to_player()

        if self.__free_camera:
            # pivot around mouse
            cx = (x - self.camera.viewport_width / 2) * -diff
            cy = (y - self.camera.viewport_height / 2) * -diff

            self.camera.move((
                self.camera.goal_position.x + cx,
                self.camera.goal_position.y + cy,
            ))

    def on_console_command(self, s):
        print(s)
        if not s:
            return
        parts = s.split(' ')
        base, args = parts[0], parts[1:]
        self.console_add_msg('>' + s)
        if base in self.__console_commands:
            self.__console_commands[base](*args)
        else:
            self.console_add_msg('unknown command. SKILL ISSUE YOU ARE A FAILURE.')

    def console_add_msg(self, line):
        self.__console_msgs.append(line)
        logging.info('CONSOLE: ' + line)

    def cmd_help(self):
        self.console_add_msg('NO ONE IS HERE TO HELP YOU. NO ONE LOVES YOU.')

    def cmd_dumpsim(self, filename=None):
        if filename is None:
            return

        if self.__history_index < 0:
            return
        submission = self.__history[:self.__history_index + 1]

        replay_state_keys = []
        for state in submission:
            if state is None:
                replay_state_keys.append(None)
                continue
            replay_state_keys.append(json.loads(state.sent_game_info.decode())["keys"])

        with open(filename, "w") as f:
            json.dump(replay_state_keys, f)

    def cmd_loadsim(self, filename=None):
        with open(filename, "r") as f:
                keys_to_send = json.load(f)

        for keys in keys_to_send:
            self.game.__dict__['raw_pressed_keys'] = set(keys) if keys is not None else set()
            self.game.tick()
            self.append_history(self.game.backup())
        self.game.__dict__['raw_pressed_keys'] = set()

    def cmd_logic(self):
        if not self.game:
            self.console_add_msg('no game')
            return
        var_map = {}
        def get_var(elem_):
            if isinstance(elem_, components.logic.LogicComponent):
                elem_ = elem_.logic_id
            elif isinstance(elem_, str):
                pass
            else:
                raise TypeError(str(type(elem_)))
            if elem_ not in var_map:
                var_map[elem_] = f'var_{len(var_map)}'
            return var_map[elem_]
        result = []
        for name, elem in self.game.logic_engine.logic_map.items():
            z3_var = get_var(elem)
            result.append(f'{z3_var} = Int("{z3_var}") # {elem.logic_id}')
        for name, elem in self.game.logic_engine.logic_map.items():
            z3_var = get_var(elem)
            print(elem.nametype, elem.logic_id)
            assert name == elem.logic_id
            match type(elem):
                case components.logic.Buffer:
                    args = f'inp={get_var(elem.inp)}'
                case components.logic.Max:
                    args = f'inps=[{", ".join(map(get_var, elem.inps))}]'
                case components.logic.Min:
                    args = f'inps=[{", ".join(map(get_var, elem.inps))}]'
                case components.logic.Add:
                    args = f'inps=[{", ".join(map(get_var, elem.inps))}], mod={elem.modulus}'
                case components.logic.Multiply:
                    args = f'inps=[{", ".join(map(get_var, elem.inps))}], mod={elem.modulus}'
                case components.logic.Invert:
                    args = f'inp={get_var(elem.inp)}, mod={elem.modulus}'
                case components.logic.Negate:
                    args = f'inp={get_var(elem.inp)}, mod={elem.modulus}'
                case components.logic.Constant:
                    args = f'value={elem.value}'
                case components.logic.Toggle:
                    varname = f'{z3_var}_index'
                    args = f'values={elem.values}, index={varname}'
                    result.append(f'{varname} = Int("{varname}")')
                    result.append(f's.add({varname} >= 0)')
                    result.append(f's.add({varname} < {len(elem.values)})')
                case components.logic.LogicDoor:
                    result.append(f's.add({get_var(elem.inp)} == 0)')
                    continue
                case t:
                    self.console_add_msg("Invalid type: " + str(t))
                    args = f'NotImplementedError()'
            z3_statement = f's.add({z3_var} == {elem.nametype}({args}))'
            result.append(z3_statement)

        z3_epilogue2 = []
        for name, elem in self.game.logic_engine.logic_map.items():
            z3_epilogue2.append(f'print("{get_var(elem)} =", m.eval({get_var(elem)}).as_long())')

        pyperclip.copy(hack_util.z3_preamble + '\n\n\n' + '\n'.join(result) + hack_util.z3_epilogue + '\n\n' + '\n'.join(z3_epilogue2))
        self.console_add_msg('Copied to clipboard')

ludicer_gui.Hackceler8 = HackedHackceler8
