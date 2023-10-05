import math
import heapq
import time

import arcade

POSSIBLE_KEYS = [
    (arcade.key.D,),
    (arcade.key.A,),
    (arcade.key.A, arcade.key.W),
    (arcade.key.D, arcade.key.W),
    (arcade.key.W,),
    (),
]

POSSIBLE_KEYS_NO_JUMP = [
    (arcade.key.D,),
    (arcade.key.A,),
    (),
]
# scroller also has POSSIBLE_KEYS + arcade.key.S
POSSIBLE_KEYS_SCROLLER = [
    (arcade.key.A,),
    (arcade.key.W,),
    (arcade.key.D,),
    (arcade.key.S,),
    (arcade.key.A, arcade.key.W),
    (arcade.key.A, arcade.key.S),
    (arcade.key.D, arcade.key.W),
    (arcade.key.D, arcade.key.S),
    (),
]

GRANULARITY = 16
PRESSING_LENGTH = 5
TIMEOUT = 5.


def get_player_coord_from_state(state):
    player_properties = state.player[1].properties
    player_x, player_y = None, None
    for key, value in player_properties:
        if key == 'x':
            player_x = value
        elif key == 'y':
            player_y = value
    assert player_x is not None and player_y is not None
    return player_x, player_y

def get_player_can_jump_from_state(state):
    player_properties = state.player[1].properties
    in_the_air, jump_override = None, None
    for key, value in player_properties:
        if key == 'in_the_air':
            in_the_air = value
        elif key == 'jump_override':
            jump_override = value
    return not in_the_air or jump_override

class QueueElement:
    def __init__(self, state, dest_x, dest_y):
        self.state = state
        self.heuristic = self.__heuristic(dest_x, dest_y)

    def __heuristic(self, dest_x, dest_y):
        player_x, player_y = get_player_coord_from_state(self.state)
        return math.hypot(player_x - dest_x, player_y - dest_y)

    def __lt__(self, other):
        return self.heuristic < other.heuristic


def get_outline(properties):
    for key, value in properties:
        if key == 'outline':
            return value
    raise Exception('No outline property found')


def get_highest_point(outline):
    max_height = -math.inf
    for i in outline:
        max_height = max(max_height, i.y)
    return max_height


def get_lowest_point(outline):
    min_height = math.inf
    for i in outline:
        min_height = min(min_height, i.y)
    return min_height


def get_rightmost_point(outline):
    max_x = -math.inf
    for i in outline:
        max_x = max(max_x, i.x)
    return max_x


def get_leftmost_point(outline):
    min_x = math.inf
    for i in outline:
        min_x = min(min_x, i.x)
    return min_x


def alias_coord(x, y):
    return x * GRANULARITY // GRANULARITY, y * GRANULARITY // GRANULARITY


def traceback(visited, x, y):
    path = []
    while True:
        states_coord = visited.pop(alias_coord(x, y))
        if states_coord is None:
            break
        path.extend(reversed(states_coord[0]))
        x, y = states_coord[1]
    return reversed(path)


def navigate(game, target_x, target_y):
    if not game.player:
        return

    initial_keys = game.__dict__['raw_pressed_keys']

    game.simulating = True
    init_state = game.backup()
    visited = {alias_coord(game.player.x, game.player.y): None}
    pq = [QueueElement(init_state, target_x, target_y)]

    start = time.time()
    try:
        while len(pq) > 0:
            if time.time() - start > TIMEOUT:
                raise TimeoutError('Path finding timed out')
            state = heapq.heappop(pq).state
            coord = get_player_coord_from_state(state)
            outline = get_outline(state.player[1].properties)
            if get_leftmost_point(outline) <= target_x <= get_rightmost_point(outline) and \
                    get_lowest_point(outline) <= target_y <= get_highest_point(outline):
                return traceback(visited, *coord)

            possible_keys = None
            if game.player.platformer_rules:
                possible_keys = POSSIBLE_KEYS if get_player_can_jump_from_state(state) else POSSIBLE_KEYS_NO_JUMP
            else:
                possible_keys = POSSIBLE_KEYS_SCROLLER
            for keys in possible_keys:
                game.restore(state)
                game.__dict__['raw_pressed_keys'] = frozenset((arcade.key.LSHIFT, *keys))

                new_states = []
                for _ in range(PRESSING_LENGTH):
                    health = game.player.health
                    game.tick()
                    if game.player.health < health - 10 or game.player.dead:
                        new_states = None
                        break
                    cx, cy, nb = game.physics_engine._get_collisions_list(game.player)
                    if len(cx):
                        new_states = None
                        break
                    for o, mpv in cy:
                        if mpv[1] > 0:
                            new_states = None
                            break
                    if new_states is None:
                        break
                    new_states.append(game.backup())
                if new_states is None:
                    continue

                new_coord = alias_coord(game.player.x, game.player.y)
                if new_coord not in visited:
                    visited[new_coord] = new_states, coord
                    heapq.heappush(pq, QueueElement(new_states[-1], target_x, target_y))
    except Exception as e:
        game.restore(init_state)
        if not isinstance(e, TimeoutError):
            raise
    finally:
        game.__dict__['raw_pressed_keys'] = initial_keys
        game.simulating = False
