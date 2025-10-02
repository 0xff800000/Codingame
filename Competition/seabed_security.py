import math
from typing import List, NamedTuple, Dict
import numpy as np
import random
import sys

random.seed(1234)

LIGHT_RADIUS = 2000
MIN_Y_FISH = 2500

DIR_MAPPING = {
    "TL": np.array([-1, -1]) / np.linalg.norm(np.array([1, 1])),
    "TR": np.array([1, -1]) / np.linalg.norm(np.array([1, 1])),
    "BL": np.array([-1, 1]) / np.linalg.norm(np.array([1, 1])),
    "BR": np.array([1, 1]) / np.linalg.norm(np.array([1, 1])),
}


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


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


class Palantir:
    def __init__(self, fish_details, monster_fish_ids):
        self.visible_fish = []
        self.radar_blips = []
        self.my_drones = []
        self.foe_drones = []
        self.all_drone_scans = []
        self.my_confirmed_scans = []
        self.foe_confirmed_scans = []
        self.escaped_fish_ids = set([])
        self.monster_fish_ids = monster_fish_ids
        self.fish_entries = {}
        for fish_id in fish_details:
            self.fish_entries[fish_id] = {
                "details": fish_details[fish_id],
                "bounding_box": {"p0": (0, 0), "p1": (9999, 9999)},
            }

    def get_fish_min_max_y(self, fish_id):
        fish_type = self.fish_entries[fish_id]["details"].type
        if fish_type == -1:
            return (2500, 10000)
        elif fish_type == 0:
            return (2500, 5000)
        elif fish_type == 1:
            return (5000, 7500)
        elif fish_type == 2:
            return (7500, 10000)
        return (0, 9999)

    def update(
        self,
        visible_fish,
        radar_blips,
        my_drones,
        foe_drones,
        all_drone_scans,
        my_confirmed_scans,
        foe_confirmed_scans,
    ):
        self.visible_fish = visible_fish
        self.radar_blips = radar_blips
        self.my_drones = my_drones
        self.foe_drones = foe_drones
        self.all_drone_scans = all_drone_scans
        self.my_confirmed_scans = my_confirmed_scans
        self.foe_confirmed_scans = foe_confirmed_scans

        ## TODO reset not visible

        # Update exact location accordinig to visible data
        for fish in visible_fish:
            self.fish_entries[fish.fish_id]["exact_location"] = {
                "pos": fish.pos,
                "speed": fish.speed,
            }

        # Combine radar blips from multiple drones
        # Each combined radar blips entry stores the position of the drone that took it
        # and the direction of the blip. This is stored for each drones
        comb_radar_blips = {}
        for drone in self.my_drones:
            if drone.drone_id not in radar_blips:
                continue
            for rb in radar_blips[drone.drone_id]:
                if rb.fish_id not in comb_radar_blips:
                    comb_radar_blips[rb.fish_id] = []
                comb_radar_blips[rb.fish_id].append(
                    {"drone_pos": drone.pos, "dir": rb.dir}
                )

        # Update bounding boxes based on combined radar blips
        for fish_id, sightings in comb_radar_blips.items():
            min_y, max_y = self.get_fish_min_max_y(fish_id)
            p0x, p0y = (0, min_y)
            p1x, p1y = (9999, max_y)

            for sight in sightings:
                drone_pos = sight["drone_pos"]
                dir = sight["dir"]

                if dir == "TL":
                    # Top-left blip: fish is to top-left of drone
                    p1x = min(p1x, drone_pos.x)
                    p1y = min(p1y, drone_pos.y)
                elif dir == "TR":
                    # Top-right blip: fish is to top-right of drone
                    p0x = max(p0x, drone_pos.x)
                    p1y = min(p1y, drone_pos.y)
                elif dir == "BL":
                    # Bottom-left blip: fish is to bottom-left of drone
                    p1x = min(p1x, drone_pos.x)
                    p0y = max(p0y, drone_pos.y)
                elif dir == "BR":
                    # Bottom-right blip: fish is to bottom-right of drone
                    p0x = max(p0x, drone_pos.x)
                    p0y = max(p0y, drone_pos.y)

            # Update bounding box
            self.fish_entries[fish_id]["bounding_box"]["p0"] = (p0x, p0y)
            self.fish_entries[fish_id]["bounding_box"]["p1"] = (p1x, p1y)

        # Update escaped fishes
        for fish_id in self.fish_entries:
            if fish_id not in comb_radar_blips:
                self.escaped_fish_ids.add(fish_id)

        # first_fish = [fish_id for fish_id in self.fish_entries][0]
        # eprint(first_fish, self.fish_entries[first_fish]["bounding_box"])
        # eprint(first_fish, comb_radar_blips[first_fish])

    def is_valid_target_fish_id(self, drone_id, fish_id):
        if (
            fish_id in self.my_confirmed_scans
            or fish_id in self.escaped_fish_ids
            or fish_id in self.monster_fish_ids
            or (
                drone_id in self.all_drone_scans
                and fish_id in self.all_drone_scans[drone_id]
            )
        ):
            return False
        return True

    def select_target(self, drone_id):
        potential_targets = [
            fish_id
            for fish_id in self.fish_entries
            if self.is_valid_target_fish_id(drone_id, fish_id)
        ]
        # eprint(potential_targets)
        drone = None
        for d in self.my_drones:
            if d.drone_id == drone_id:
                drone = d
        if drone is None or len(potential_targets) == 0:
            return None, None

        direction = np.array([0, 0])
        target_dir = {fish_id: np.array([0, 0]) for fish_id in potential_targets}

        # Compute target score
        target_score = {}
        for fish_id in potential_targets:
            # Distance visible
            distance_vis_score = 0
            if fish_id in [fish.fish_id for fish in self.visible_fish]:
                rel_x = (
                    self.fish_entries[fish_id]["exact_location"]["pos"].x - drone.pos.x
                )
                rel_y = (
                    self.fish_entries[fish_id]["exact_location"]["pos"].y - drone.pos.y
                )
                distance = math.hypot(rel_x, rel_y)
                distance_vis_score = 1.0 * (1 - distance / LIGHT_RADIUS)

                target_dir[fish_id] = np.array(
                    [
                        self.fish_entries[fish_id]["exact_location"]["pos"].x,
                        self.fish_entries[fish_id]["exact_location"]["pos"].y,
                    ]
                )

            # Bounding box size
            bbox_size_score = 0
            p0x, p0y = self.fish_entries[fish_id]["bounding_box"]["p0"]
            p1x, p1y = self.fish_entries[fish_id]["bounding_box"]["p1"]
            bbox_surface = (p1x - p0x) * (p1y - p0y)
            bbox_size_score = 1.0 * (1 - bbox_surface / (10e4**2))

            # Bounding box distance
            bbox_distance_score = 0
            center_bbox_x = p0x + (p1x - p0x) / 2
            center_bbox_y = p0y + (p1y - p0y) / 2
            bbox_dist = math.hypot(
                center_bbox_x - drone.pos.x,
                center_bbox_y - drone.pos.y,
            )
            bbox_distance_score = 1.0 * (1 - bbox_dist / 9999)

            if np.linalg.norm(target_dir[fish_id]) == 0:
                target_dir[fish_id] = np.array(
                    [
                        center_bbox_x,
                        center_bbox_y,
                    ]
                )

            # Risk
            risk_score = 0

            target_score[fish_id] = sum(
                [distance_vis_score, bbox_size_score, bbox_distance_score, risk_score]
            )

        # eprint(target_score)
        best_target = max(target_score, key=target_score.get)
        eprint(best_target)
        return best_target, target_dir[best_target]

    def get_monsters_to_avoid(self, drone_id, danger_radius=3000):
        """
        Returns a list of (monster_id, avoid_vector) for monsters within danger_radius
        """
        drone = next((d for d in self.my_drones if d.drone_id == drone_id), None)
        if drone is None:
            return []

        monsters_to_avoid = []

        # 1. Visible monsters
        for f in self.visible_fish:
            if f.fish_id in self.monster_fish_ids:
                rel_x = drone.pos.x - f.pos.x
                rel_y = drone.pos.y - f.pos.y
                dist = math.hypot(rel_x, rel_y)

                if dist < danger_radius:
                    # Normalize vector away from monster
                    dx, dy = (rel_x / dist, rel_y / dist) if dist > 0 else (0, 0)
                    monsters_to_avoid.append(
                        (f.fish_id, np.array([dx, dy], dtype=np.float64))
                    )

        # 2. Bounding box monsters (not visible but constrained by radar)
        for fish_id in self.monster_fish_ids:
            if (
                fish_id in self.fish_entries
                and "exact_location" not in self.fish_entries[fish_id]
            ):
                # Use bbox center as an approximate location
                p0x, p0y = self.fish_entries[fish_id]["bounding_box"]["p0"]
                p1x, p1y = self.fish_entries[fish_id]["bounding_box"]["p1"]
                cx, cy = (p0x + p1x) / 2, (p0y + p1y) / 2

                rel_x = drone.pos.x - cx
                rel_y = drone.pos.y - cy
                dist = math.hypot(rel_x, rel_y)

                bbox_area = (p1x - p0x) * (p1y - p0y)

                # if dist < danger_radius and dist**2 > bbox_area:
                if dist < danger_radius:
                    dx, dy = (rel_x / dist, rel_y / dist) if dist > 0 else (0, 0)
                    monsters_to_avoid.append(
                        (fish_id, np.array([dx, dy], dtype=np.float64))
                    )

        return monsters_to_avoid


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
        self.stash_size = 4  # Amount of scanned fish before surfacing
        self.monster_ids_to_avoid = {}
        self.monster_avoid_tics = 3
        self.min_avoid_dist = 3000
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

    def fish_distance(self, fish):
        return math.sqrt(
            (fish.pos.x - self.pos.x) ** 2 + (fish.pos.y - self.pos.y) ** 2
        )

    def get_closest_visible_fish(self, visible_fish):
        candidates = (
            f
            for f in visible_fish
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
        monster_blip_dirs = [
            rb.dir
            for rb in [a for a in radar_blips if a.fish_id in self.banned_fish_ids]
        ]
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

    def get_wall_avoidance_vector(self, drone, monster_avoid_vector, margin=800):
        """Returns a vector pushing the drone away from walls if too close."""
        dx, dy = 0, 0

        if drone.pos.x < margin or drone.pos.x > 9999 - margin:
            dy += monster_avoid_vector[1] / abs(monster_avoid_vector[1])

        if drone.pos.y < margin or drone.pos.y > 9999 - margin:
            dx += monster_avoid_vector[0] / abs(monster_avoid_vector[0])

        if dx == 0 and dy == 0:
            return np.array([0, 0])

        norm = math.hypot(dx, dy)
        return np.array([dx / norm, dy / norm])

    def do_action(self, visible_fish, radar_blips, palantir):
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

        monsters = palantir.get_monsters_to_avoid(self.drone_id)
        if monsters:
            self.state = "avoid_monster"
        if self.state == "avoid_monster" and len(monsters) == 0:
            self.state = "search_fish"

        # State transition
        if self.state == "search_fish":
            if (
                len(self.scans) == self.fish_count
                or len(self.scans) - len(self.confirmed_scans) >= self.stash_size
            ):
                self.state = "surface"
        elif self.state == "surface":
            if self.pos.y == 0:
                self.state = "search_fish"

        if self.state == "surface":
            light = 0
            target_x = self.pos.x
            target_y = 0

        elif self.state == "search_fish":
            fish_id, direction = palantir.select_target(self.drone_id)
            if fish_id is not None:
                target_x = round(direction[0])
                target_y = round(direction[1])
            eprint(fish_id, target_x, target_y, self.drone_id)

        elif self.state == "avoid_monster":
            move_dir = np.array([0, 0], dtype=np.float64)
            for monster_id, avoid_vec in monsters:
                move_dir += avoid_vec

            avoid_walls = self.get_wall_avoidance_vector(drone, move_dir)
            move_dir += avoid_walls * 1.5
            move_dir /= np.linalg.norm(move_dir)
            target_x = round(drone.pos.x + 1000 * move_dir[0])
            target_y = round(drone.pos.y + 1000 * move_dir[1])
            dbg_str += f"{monsters}"

        target_x = max(min(round(target_x), 9999), 0)
        target_y = max(min(round(target_y), 9999), 0)

        for m_id in self.monster_ids_to_avoid:
            self.monster_ids_to_avoid[m_id] -= 1

        self.last_state = self.state

        light_dbg = "" if light == 0 else "💡"
        print(
            f"MOVE {target_x} {target_y} {light} {self.drone_id} {light_dbg} {self.get_state_emoji()} {dbg_str}"
        )


fish_details: Dict[int, FishDetail] = {}
monster_fish_ids = []
fish_count = int(input())
for _ in range(fish_count):
    fish_id, color, _type = map(int, input().split())
    fish_details[fish_id] = FishDetail(color, _type)
    if _type == -1:
        monster_fish_ids.append(fish_id)
print(monster_fish_ids, file=sys.stderr)

palantir = Palantir(fish_details, monster_fish_ids)

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
            drone_ais.append(
                DroneAI(drone_id, pos, dead == 1, battery, fish_count, monster_fish_ids)
            )
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
    all_drone_scans = {d.drone_id: [] for d in my_drones + foe_drones}

    drone_scan_count = int(input())
    for _ in range(drone_scan_count):
        drone_id, fish_id = map(int, input().split())
        all_drone_scans[drone_id].append(fish_id)
        drone_by_id[drone_id].scans.append(fish_id)
        if drone_id in my_drone_ids:
            for d in drone_ais:
                d.append_scans(drone_id, fish_id)
    # eprint(all_drone_scans)

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

    palantir.update(
        visible_fish,
        my_radar_blips,
        my_drones,
        foe_drones,
        all_drone_scans,
        my_scans,
        foe_scans,
    )

    for drone in drone_ais:
        drone.do_action(visible_fish, my_radar_blips[drone.drone_id], palantir)
        palantir.select_target(drone.drone_id)
        # eprint(palantir.get_monsters_to_avoid(drone.drone_id))
