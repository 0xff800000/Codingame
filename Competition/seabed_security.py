import math
from typing import List, NamedTuple, Dict
import numpy as np
import random
import sys

random.seed(1234)

dir_mapping = {
    "TL": np.array([-1,-1]) / np.linalg.norm(np.array([1,1])),
    "TR": np.array([1,-1]) / np.linalg.norm(np.array([1,1])),
    "BL": np.array([-1,1]) / np.linalg.norm(np.array([1,1])),
    "BR": np.array([1,1]) / np.linalg.norm(np.array([1,1])),
}

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# Define the data structures as namedtuples
class Vector(NamedTuple):
    x: int
    y: int

class FishDetail(NamedTuple):
    color: int
    type: int

class Fish(NamedTuple):
    fish_id: int
    pos: Vector
    speed: Vector
    detail: FishDetail

class RadarBlip(NamedTuple):
    fish_id: int
    dir: str

class Drone(NamedTuple):
    drone_id: int
    pos: Vector
    dead: bool
    battery: int
    scans: List[int]

LIGHT_RADIUS = 2000
MIN_Y_FISH = 2500

class DroneAI:
    def __init__(self, drone_id, pos, dead, battery, fish_count, banned_faish_ids):
        self.drone_id = drone_id
        self.pos = pos
        self.dead = dead
        self.battery = battery
        self.scans = set([])
        self.confirmed_scans = []
        self.fish_count = fish_count
        self.state = "search_fish"
        self.radar_blip_target = None
        self.banned_fish_ids = set(banned_faish_ids)
        self.stash_size = 4 # Amount of scanned fish before surfacing
        self.monster_ids_to_avoid = {}
        self.monster_avoid_tics = 3
        self.min_avoid_dist = 1000
        self.last_state = None
    
    def update(self, pos, dead, battery, confirmed_scans):
        self.pos = pos
        self.dead = dead
        self.battery = battery
        self.confirmed_scans = confirmed_scans
    
    def append_scans(self, drone_id, fish_id):
        if drone_id != self.drone_id:
            return
        if fish_id not in self.confirmed_scans:
            self.scans.add(fish_id)

    def fish_distance(self,fish):
        return math.sqrt((fish.pos.x - self.pos.x)**2 + (fish.pos.y - self.pos.y)**2)

    def get_closest_visible_fish(self, visible_fish):
        candidates = (
            f for f in visible_fish
            if f.fish_id not in self.confirmed_scans
            and f.fish_id not in self.banned_fish_ids
            and f.fish_id not in self.scans
        )
        return min(candidates, key=self.fish_distance, default=None)
    
    def get_state_emoji(self):
        if self.state == "avoid_monster":
            return "🚨"
        elif self.state == "search_fish":
            return "📡🔎"
        elif self.state == "surface":
            return "⬆️"
    
    def radar_is_blip_towards_monster(self, target_blip, radar_blips):
        monster_blip_dirs = [rb.dir for rb in [a for a in radar_blips if a.fish_id in self.banned_fish_ids]]
        if target_blip.dir in monster_blip_dirs:
            return True
        return False
    
    def get_light_action(self):
        if self.last_state == "avoid_monster" and self.state != "avoid_monster":
            return 1

        if self.battery < 20:
            return 0

        if self.state == "surface":
            return 0
        
        if self.state == "avoid_monster":
            return 0
        
        if self.pos.y + LIGHT_RADIUS > MIN_Y_FISH:
            return 1
        
        return 0

    
    def get_monster_avoid_move(self, monster):
        # Relative position (drone -> monster)
        rel_x = self.pos.x - monster.pos.x
        rel_y = self.pos.y - monster.pos.y
        rel_dist = math.hypot(rel_x, rel_y) or 1

        # Monster velocity
        vx, vy = monster.speed.x, monster.speed.y
        speed_mag = math.hypot(vx, vy)

        if speed_mag < 1e-6:
            # Monster basically stationary → flee directly away
            dx, dy = rel_x / rel_dist, rel_y / rel_dist
        else:
            # Two orthogonal directions to velocity
            ortho1 = (-vy, vx)
            ortho2 = (vy, -vx)

            # Pick orthogonal vector that points more away
            dot1 = rel_x * ortho1[0] + rel_y * ortho1[1]
            dot2 = rel_x * ortho2[0] + rel_y * ortho2[1]
            ox, oy = ortho1 if dot1 > dot2 else ortho2

            # Normalize orthogonal
            o_len = math.hypot(ox, oy) or 1
            ox, oy = ox / o_len, oy / o_len

            # Normalize direct-away
            ax, ay = rel_x / rel_dist, rel_y / rel_dist

            # Blend: closer monster → stronger weight on direct-away
            away_weight = min(1.0, 3000 / rel_dist)  # up to full weight if <3k
            ortho_weight = 1.0 - away_weight

            dx = ax * away_weight + ox * ortho_weight
            dy = ay * away_weight + oy * ortho_weight

            # Normalize final escape vector
            d_len = math.hypot(dx, dy) or 1
            dx, dy = dx / d_len, dy / d_len

        return np.array([dx, dy])

    def do_action(self, visible_fish, radar_blips):
        light = self.get_light_action()
        target_x = self.pos[0]
        target_y = 0
        dbg_str = ""
        radar_blip_ids = [rb.fish_id for rb in radar_blips]

        # Remove confirmed scans from scans
        for fish_id in self.confirmed_scans:
            if fish_id in self.scans:
                self.scans.remove(fish_id)

        if self.dead:
            self.scans = set([])
            print("WAIT 0")
            return

        # detect monsters
        monsters = [f for f in visible_fish if f.detail.type == -1]
        closest_monster = None
        if monsters:
            closest_monster = min(monsters, key=lambda m: self.fish_distance(m))
            eprint(closest_monster)
            if self.fish_distance(closest_monster) < self.min_avoid_dist:
                self.state = "avoid_monster"

        # State transition
        if self.state == "search_fish":
            if len(self.scans) == self.fish_count or len(self.scans) - len(self.confirmed_scans) >= self.stash_size:
                self.state = "surface"
        elif self.state == "surface":
            if self.pos.y == 0:
                self.state = "search_fish"
        elif self.state == "avoid_monster":
            if len(self.monster_ids_to_avoid) == 0 and closest_monster is not None and self.fish_distance(closest_monster) > self.min_avoid_dist:
                self.state = "search_fish"

        if self.state == "surface":
            light = 0
            target_x = self.pos.x
            target_y = 0

        elif self.state == "search_fish":
            # Target closest visible fish
            target_fish = self.get_closest_visible_fish(visible_fish)

            if target_fish is not None:
                target_x = target_fish.pos.x
                target_y = target_fish.pos.y
                dbg_str += f" {target_fish.fish_id}"
            else:
                if (
                    self.radar_blip_target is not None
                    and (self.radar_blip_target.fish_id in self.scans
                    or self.radar_blip_target.fish_id in self.confirmed_scans
                    or self.radar_blip_target.fish_id in self.banned_fish_ids
                    or self.radar_blip_target.fish_id not in radar_blip_ids
                    #or self.radar_is_blip_towards_monster(self.radar_blip_target,radar_blips)
                    )
                    ):
                    self.radar_blip_target = None

                if self.radar_blip_target is None:
                    # Pick new unexplored radar blip
                    potential_radar_blips = [
                        rb for rb in radar_blips
                        if rb.fish_id not in self.confirmed_scans
                        and rb.fish_id not in self.banned_fish_ids
                        and rb.fish_id not in self.scans
                    ]
                    random.shuffle(potential_radar_blips)
                    if len(potential_radar_blips) > 0:
                        self.radar_blip_target = potential_radar_blips[0]
                else:
                    # Update blip
                    for rb in radar_blips:
                        if rb.fish_id == self.radar_blip_target.fish_id:
                            self.radar_blip_target = rb
                            break

                if self.radar_blip_target is not None:
                    dx, dy = dir_mapping[self.radar_blip_target.dir]
                    target_x = round(self.pos.x + 1000 * dx)
                    target_y = round(self.pos.y + 1000 * dy)
                    dbg_str += f"{self.radar_blip_target.fish_id}"
                else:
                    dbg_str += f" ERROR"
        
        elif self.state == "avoid_monster":
            # Visible monsters
            monster_vec = [self.get_monster_avoid_move(m) for m in monsters]
            eprint(monster_vec)
            dx, dy = (0,0)
            for mv in monster_vec:
                dx += mv[0] / len(monster_vec)
                dy += mv[1] / len(monster_vec)
            
            # Radar monster
            for m in monsters:
                self.monster_ids_to_avoid[m.fish_id] = self.monster_avoid_tics

            for m_id in self.monster_ids_to_avoid:
                for rb in radar_blips:
                    if rb.fish_id == m_id:
                        _dx, _dy = dir_mapping[rb.dir]
                        dx -= _dx / len(self.monster_ids_to_avoid)
                        dy -= _dy / len(self.monster_ids_to_avoid)

            
            rem_id = [ m_id for m_id in self.monster_ids_to_avoid if self.monster_ids_to_avoid[m_id] <= 0 ]
            for m_id in rem_id:
                del self.monster_ids_to_avoid[m_id]
            dbg_str += str(self.monster_ids_to_avoid)

            
            target_x = round(self.pos.x + 1000 * dx)
            target_y = round(self.pos.y + 1000 * dy)

        target_x = max(min(round(target_x), 9999), 0)
        target_y = max(min(round(target_y), 9999), 0)


        for m_id in self.monster_ids_to_avoid:
            self.monster_ids_to_avoid[m_id] -= 1

        self.last_state = self.state

        light_dbg = "" if light == 0 else "💡"
        print(f"MOVE {target_x} {target_y} {light} {self.drone_id} {light_dbg} {self.get_state_emoji()} {dbg_str}")


fish_details: Dict[int, FishDetail] = {}
monster_fish_ids = []
fish_count = int(input())
for _ in range(fish_count):
    fish_id, color, _type = map(int, input().split())
    fish_details[fish_id] = FishDetail(color, _type)
    if _type == -1:
        monster_fish_ids.append(fish_id)
print(monster_fish_ids, file=sys.stderr)

# game loop
drone_ais = []
while True:
    my_scans: List[int] = []
    foe_scans: List[int] = []
    drone_by_id: Dict[int, Drone] = {}
    my_drones: List[Drone] = []
    foe_drones: List[Drone] = []
    visible_fish: List[Fish] = []
    my_radar_blips: Dict[int, List[RadarBlip]] = {}

    my_score = int(input())
    foe_score = int(input())

    my_scan_count = int(input())
    for _ in range(my_scan_count):
        fish_id = int(input())
        my_scans.append(fish_id)

    foe_scan_count = int(input())
    for _ in range(foe_scan_count):
        fish_id = int(input())
        foe_scans.append(fish_id)

    my_drone_count = int(input())

    for i in range(my_drone_count):
        drone_id, drone_x, drone_y, dead, battery = map(int, input().split())
        pos = Vector(drone_x, drone_y)
        if len(drone_ais) < my_drone_count:
            drone_ais.append(DroneAI(drone_id, pos, dead == 1, battery, fish_count, monster_fish_ids))
        drone_ais[i].update(pos, dead == 1, battery, my_scans)
        drone = Drone(drone_id, pos, dead == 1, battery, [])
        drone_by_id[drone_id] = drone
        my_drones.append(drone)
        my_radar_blips[drone_id] = []

    foe_drone_count = int(input())
    for _ in range(foe_drone_count):
        drone_id, drone_x, drone_y, dead, battery = map(int, input().split())
        pos = Vector(drone_x, drone_y)
        drone = Drone(drone_id, pos, dead == 1, battery, [])
        drone_by_id[drone_id] = drone
        foe_drones.append(drone)
    
    my_drone_ids = [d.drone_id for d in my_drones]

    drone_scan_count = int(input())
    for _ in range(drone_scan_count):
        drone_id, fish_id = map(int, input().split())
        drone_by_id[drone_id].scans.append(fish_id)
        if drone_id in my_drone_ids:
            for d in drone_ais:
                d.append_scans(drone_id, fish_id)

    visible_fish_count = int(input())
    for _ in range(visible_fish_count):
        fish_id, fish_x, fish_y, fish_vx, fish_vy = map(int, input().split())
        pos = Vector(fish_x, fish_y)
        speed = Vector(fish_vx, fish_vy)
        visible_fish.append(Fish(fish_id, pos, speed, fish_details[fish_id]))

    my_radar_blip_count = int(input())
    for _ in range(my_radar_blip_count):
        drone_id, fish_id, dir = input().split()
        drone_id = int(drone_id)
        fish_id = int(fish_id)
        my_radar_blips[drone_id].append(RadarBlip(fish_id, dir))

    for drone in drone_ais:
        drone.do_action(visible_fish, my_radar_blips[drone.drone_id])

