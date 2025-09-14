import collections
import time
import os
import random

# --- Constants ---
COLORS = {
    "RED": "\033[91m", "GREEN": "\033[92m", "YELLOW": "\033[93m",
    "BLUE": "\033[94m", "WHITE": "\033[97m", "RESET": "\033[0m",
}

MAP_LAYOUT = """
1.FF.M...2
.F.M.M.F..
F..MM.F.F.
..M..F..M.
M....M..FM
MF..M....M
.M..F..M..
.F.F.MM..F
..F.M.M.F.
4...M.FF.3
"""

# --- Game Classes ---

class Tile:
    def __init__(self, x, y, tile_type):
        self.x, self.y = x, y
        self.tile_type = tile_type
        self.owner = None

class Legion:
    def __init__(self, owner, x, y):
        self.owner = owner
        self.x, self.y = x, y
        self.has_moved = False

class Kingdom:
    def __init__(self, name, ai_type, capital_pos, color_code):
        self.name = name
        self.ai_type = ai_type
        self.capital_pos = capital_pos
        self.color = color_code
        self.gold = 5
        self.is_eliminated = False
        self.recruit_cost = 5
        self.movement_range = 1
        if ai_type == "Crimson": self.recruit_cost = 4
        if ai_type == "Verdant": self.movement_range = 2

    def __repr__(self):
        return f"{self.color}{self.name}{COLORS['RESET']}"

    def take_turn(self, board):
        # This function is being called from a loop, so we can skip the print statements for speed.
        # print(f"\n--- {self}'s Turn (Gold: {self.gold}) ---")

        ### FIX 1: CONDITIONAL CAPITAL INCOME ###
        # Capital income is only granted if the kingdom controls its capital.
        income = 0
        if board.get_tile(*self.capital_pos).owner == self:
            income = 3
        
        forest_income = sum(1 for tile in board.get_tiles_owned_by(self) if tile.tile_type == 'FOREST')
        if self.ai_type == "Golden": forest_income *= 2
        
        self.gold += income + forest_income
        # print(f"Income: +{income+forest_income} Gold. Total: {self.gold}")

        my_legions = board.get_legions_of(self)
        upkeep_cost = len(my_legions)
        # print(f"Upkeep: -{upkeep_cost} Gold for {upkeep_cost} Legions.")
        self.gold -= upkeep_cost

        ### FIX 2: CORRECTED BANKRUPTCY LOGIC ###
        # The original script incorrectly calculated how many to disband and then reset gold to 0.
        # This version correctly disbands one-by-one until gold is non-negative.
        while self.gold < 0 and my_legions:
            # print(f"{self} is bankrupt (Gold: {self.gold})! Disbanding a Legion.")
            disbanded_legion = random.choice(my_legions)
            board.legions.remove(disbanded_legion)
            my_legions.remove(disbanded_legion)
            self.gold += 1 # Recoup the upkeep cost for the now-disbanded legion.
        
        # A kingdom can remain in debt if it runs out of legions to disband.
        # if self.gold < 0:
            # print(f"{self} has no more Legions to disband and remains in debt at {self.gold} Gold.")
        
        # Reset movement for the legions that survived upkeep
        for legion in my_legions:
            legion.has_moved = False
            
        ai_function = getattr(self, f"_ai_{self.ai_type.lower()}")
        ai_function(board)
        
        if self.ai_type == "Azure":
            spoils = board.check_azure_spoils(self)
            if spoils > 0:
                # print(f"{self} gains {spoils} gold from 'Spoils of War'.")
                self.gold += spoils

    # --- AI Implementations ---
    def _ai_crimson(self, board):
        primary_target_kingdom = None
        min_dist = float('inf')
        for enemy in board.kingdoms:
            if enemy != self and not enemy.is_eliminated:
                path = board.find_path(self.capital_pos, enemy.capital_pos)
                dist = len(path) if path else float('inf')
                if dist < min_dist:
                    min_dist, primary_target_kingdom = dist, enemy
        if not primary_target_kingdom: return
        # print(f"{self} has designated {primary_target_kingdom} as its primary target!")
        capital_legion = board.get_legion_at(*self.capital_pos)
        if capital_legion and not capital_legion.has_moved:
            board.move_legion_towards(capital_legion, *primary_target_kingdom.capital_pos)
        if self.gold >= self.recruit_cost and not board.get_legion_at(*self.capital_pos):
            board.create_legion(self, *self.capital_pos)
            self.gold -= self.recruit_cost
            # print(f"{self} recruits a new Legion.")
        for legion in board.get_legions_of(self):
            if not legion.has_moved:
                target = board.find_closest_enemy_of_kingdom(legion, primary_target_kingdom)
                if target: board.move_legion_towards(legion, target.x, target.y)

    def _ai_golden(self, board):
        if self.gold >= self.recruit_cost and not board.get_legion_at(*self.capital_pos):
            board.create_legion(self, *self.capital_pos)
            self.gold -= self.recruit_cost
            # print(f"{self} recruits a new Legion.")
        crusade_target = None
        my_legion_count = len(board.get_legions_of(self))
        for enemy in board.kingdoms:
            if enemy != self and not enemy.is_eliminated:
                if self.gold > enemy.gold and my_legion_count > len(board.get_legions_of(enemy)):
                    crusade_target = enemy
                    break
        # if crusade_target:
            # print(f"{self} declares a 'Golden Crusade' against {crusade_target}!")
        for legion in board.get_legions_of(self):
            if legion.has_moved: continue
            enemy_near_capital = board.find_closest_enemy_structure_or_unit(board.get_tile(*self.capital_pos), max_dist=4)
            if enemy_near_capital:
                board.move_legion_towards(legion, enemy_near_capital.x, enemy_near_capital.y)
                continue
            if crusade_target:
                target = board.find_closest_enemy_of_kingdom(legion, crusade_target)
                if target: board.move_legion_towards(legion, target.x, target.y)
                continue
            target_forest = board.find_closest_unclaimed_tile_type(legion, 'FOREST')
            if target_forest:
                board.move_legion_towards(legion, target_forest.x, target_forest.y)
                continue
            border_tile = board.find_closest_border_tile(legion)
            if border_tile: board.move_legion_towards(legion, border_tile.x, border_tile.y)

    def _ai_verdant(self, board):
        if self.gold >= self.recruit_cost and not board.get_legion_at(*self.capital_pos):
            board.create_legion(self, *self.capital_pos)
            self.gold -= self.recruit_cost
            # print(f"{self} recruits a new Legion.")
        unclaimed_tiles = sum(1 for r in board.grid for t in r if not t.owner and t.tile_type != 'MOUNTAIN')
        is_constrict_phase = unclaimed_tiles < (board.width * board.height * 0.20)
        hunt_target = None
        if is_constrict_phase:
            min_territory = float('inf')
            for enemy in board.kingdoms:
                if enemy != self and not enemy.is_eliminated:
                    territory_size = len(board.get_tiles_owned_by(enemy))
                    if territory_size < min_territory:
                        min_territory, hunt_target = territory_size, enemy
            # if hunt_target: print(f"{self} enters Constriction Phase, hunting {hunt_target}!")
        for legion in board.get_legions_of(self):
            if legion.has_moved: continue
            if hunt_target:
                target = board.find_closest_enemy_of_kingdom(legion, hunt_target)
                if target: board.move_legion_towards(legion, target.x, target.y)
            else:
                target = board.find_closest_unclaimed_tile(legion)
                if target: board.move_legion_towards(legion, target.x, target.y)

    def _ai_azure(self, board):
        avg_legions = board.get_average_enemy_legion_count(self)
        if self.gold >= self.recruit_cost and len(board.get_legions_of(self)) < avg_legions and not board.get_legion_at(*self.capital_pos):
            board.create_legion(self, *self.capital_pos)
            self.gold -= self.recruit_cost
            # print(f"{self} recruits a new Legion.")
        weakest = board.find_weakest_kingdom(self)
        is_attack_mode = False
        if weakest and len(board.get_legions_of(weakest)) < len(board.get_legions_of(self)) * 0.7:
            is_attack_mode = True
            # print(f"{self} identifies {weakest} as a vulnerable target!")
        for legion in board.get_legions_of(self):
            if legion.has_moved: continue
            if is_attack_mode and weakest:
                board.move_legion_towards(legion, *weakest.capital_pos)
            else:
                target = board.find_closest_unoccupied_enemy_tile(legion)
                if target: board.move_legion_towards(legion, target.x, target.y)
                else:
                    border_tile = board.find_closest_border_tile(legion)
                    if border_tile: board.move_legion_towards(legion, border_tile.x, border_tile.y)


class GameBoard:
    def __init__(self, layout):
        self.width, self.height = 0, 0
        self.grid = self._parse_layout(layout)
        self.kingdoms = []
        self.legions = []
        self.combat_events_this_turn = []

    def _parse_layout(self, layout):
        lines = layout.strip().split('\n')
        self.height = len(lines)
        self.width = len(lines[0])
        grid = [[None for _ in range(self.width)] for _ in range(self.height)]
        self.capital_starts = {}
        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                tile_type = {'F': 'FOREST', 'M': 'MOUNTAIN'}.get(char, 'PLAINS')
                if char.isdigit():
                    tile_type = 'CAPITAL'
                    self.capital_starts[int(char)] = (x, y)
                grid[y][x] = Tile(x, y, tile_type)
        return grid

    def setup_game(self):
        k1 = Kingdom("Crimson Empire", "Crimson", self.capital_starts[1], COLORS['RED'])
        k2 = Kingdom("Golden Republic", "Golden", self.capital_starts[2], COLORS['YELLOW'])
        k3 = Kingdom("Verdant Swarm", "Verdant", self.capital_starts[3], COLORS['GREEN'])
        k4 = Kingdom("Azure Syndicate", "Azure", self.capital_starts[4], COLORS['BLUE'])
        self.kingdoms = [k1, k2, k3, k4]
        for k in self.kingdoms:
            self.get_tile(*k.capital_pos).owner = k
            self.create_legion(k, *k.capital_pos)

    def run_simulation(self):
        turn_count = 1
        while len([k for k in self.kingdoms if not k.is_eliminated]) > 1:
            # os.system('cls' if os.name == 'nt' else 'clear')
            # print(f"====== ROUND {turn_count} ======")
            # self.print_board()
            self.combat_events_this_turn = []
            for kingdom in self.kingdoms:
                if not kingdom.is_eliminated:
                    kingdom.take_turn(self)
            self._check_capital_conquests()
            turn_count += 1
            if turn_count > 300:
                print(f'ANSWER="DRAW"')
                return
                
        winner = [k for k in self.kingdoms if not k.is_eliminated][0]
        # os.system('cls' if os.name == 'nt' else 'clear')
        # self.print_board()
        # print(f"\n\n====== GAME OVER ======\nWinner: {winner} in {turn_count - 1} rounds!")
        print(f'ANSWER="{winner.name}"')

    def print_board(self):
        print("   " + "".join([f"{i:<2}" for i in range(self.width)]))
        for y in range(self.height):
            row_str = f"{y:<2} "
            for x in range(self.width):
                tile, legion = self.grid[y][x], self.get_legion_at(x, y)
                char = {'FOREST': 'F', 'MOUNTAIN': 'M', 'CAPITAL': 'C'}.get(tile.tile_type, '.')
                if legion:
                    row_str += f"{legion.owner.color}L {COLORS['RESET']}"
                elif tile.owner:
                    row_str += f"{tile.owner.color}{char.lower()} {COLORS['RESET']}"
                else:
                    row_str += f"{COLORS['WHITE']}{char} {COLORS['RESET']}"
            print(row_str)

    def get_tile(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height: return self.grid[y][x]
        return None

    def get_legion_at(self, x, y):
        return next((l for l in self.legions if l.x == x and l.y == y), None)

    def create_legion(self, owner, x, y):
        if not self.get_legion_at(x, y):
            self.legions.append(Legion(owner, x, y))
            return True
        return False
    
    def move_legion_towards(self, legion, target_x, target_y):
        if legion.has_moved: return
        
        start_pos = (legion.x, legion.y)
        path = self.find_path(start_pos, (target_x, target_y))
        if not path or len(path) <= 1:
            legion.has_moved = True
            return

        for i in range(1, legion.owner.movement_range + 1):
            if i >= len(path): break
            next_x, next_y = path[i]
            enemy_legion = self.get_legion_at(next_x, next_y)
            if enemy_legion and enemy_legion.owner != legion.owner:
                self._handle_combat(legion, enemy_legion, start_pos)
                break 
            elif not enemy_legion:
                legion.x, legion.y = next_x, next_y
                self.get_tile(next_x, next_y).owner = legion.owner
                start_pos = (legion.x, legion.y)
            else: break
        legion.has_moved = True

    def _handle_combat(self, attacker, defender, attacker_start_pos):
        # print(f"COMBAT: {attacker.owner}'s Legion attacks {defender.owner}'s Legion!")
        self.combat_events_this_turn.append({
            'attacker': attacker.owner, 'defender': defender.owner, 'location': (defender.x, defender.y)})
        
        is_supported = False
        for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
            support_x, support_y = attacker_start_pos[0] + dx, attacker_start_pos[1] + dy
            ally_legion = self.get_legion_at(support_x, support_y)
            if ally_legion and ally_legion.owner == attacker.owner and ally_legion != attacker:
                is_supported = True
                break
        
        self.legions.remove(defender)
        if is_supported:
            # print(f"Supported attack! {attacker.owner}'s Legion survives!")
            attacker.x, attacker.y = defender.x, defender.y
            self.get_tile(defender.x, defender.y).owner = attacker.owner
        else:
            # print("Unsupported attack! Both Legions are destroyed.")
            self.legions.remove(attacker)
            self.get_tile(defender.x, defender.y).owner = None

    def _check_capital_conquests(self):
        for k_defend in self.kingdoms:
            if k_defend.is_eliminated: continue
            occupying_legion = self.get_legion_at(*k_defend.capital_pos)
            if occupying_legion and occupying_legion.owner != k_defend:
                k_attack = occupying_legion.owner
                # print(f"MAJOR EVENT: {k_attack} has captured the capital of {k_defend}!")
                k_attack.gold += k_defend.gold
                for tile in self.get_tiles_owned_by(k_defend):
                    tile.owner = k_attack
                # Remove all of the defeated kingdom's legions
                for legion in self.get_legions_of(k_defend):
                    if legion in self.legions:
                        self.legions.remove(legion)
                k_defend.is_eliminated = True
    
    def get_legions_of(self, kingdom): return [l for l in self.legions if l.owner == kingdom]
    def get_tiles_owned_by(self, kingdom): return [t for row in self.grid for t in row if t.owner == kingdom]

    def find_path(self, start_pos, end_pos):
        q = collections.deque([[start_pos]])
        visited = {start_pos}
        while q:
            path = q.popleft()
            x, y = path[-1]
            if (x, y) == end_pos: return path
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                nx, ny = x + dx, y + dy
                if self.get_tile(nx, ny) and self.get_tile(nx, ny).tile_type != 'MOUNTAIN' and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    q.append(list(path) + [(nx, ny)])
        return None

    def find_closest_target(self, legion, target_list):
        closest, min_dist = None, float('inf')
        for target in target_list:
            path = self.find_path((legion.x, legion.y), (target.x, target.y))
            if path and len(path) < min_dist:
                min_dist, closest = len(path), target
        return closest

    def find_closest_enemy_structure_or_unit(self, start_tile, max_dist=float('inf')):
        targets = []
        for k in self.kingdoms:
            if k != start_tile.owner and not k.is_eliminated: targets.append(self.get_tile(*k.capital_pos))
        for l in self.legions:
            if l.owner != start_tile.owner: targets.append(l)
        
        class Pos:
            def __init__(self, x, y): self.x, self.y = x, y
        proxies = [Pos(t.x, t.y) for t in targets]
        closest, min_dist_val = None, float('inf')
        for target in proxies:
            path = self.find_path((start_tile.x, start_tile.y), (target.x, target.y))
            if path and len(path) < min_dist_val and len(path) <= max_dist:
                min_dist_val, closest = len(path), target
        return closest
        
    def find_closest_enemy_of_kingdom(self, legion, target_kingdom):
        targets = self.get_legions_of(target_kingdom) + [self.get_tile(*target_kingdom.capital_pos)]
        class Pos:
            def __init__(self, x, y): self.x, self.y = x, y
        return self.find_closest_target(legion, [Pos(t.x, t.y) for t in targets])

    def find_closest_unclaimed_tile_type(self, legion, tile_type):
        targets = [t for r in self.grid for t in r if not t.owner and t.tile_type == tile_type]
        return self.find_closest_target(legion, targets)

    def find_closest_unclaimed_tile(self, legion):
        targets = [t for r in self.grid for t in r if not t.owner and t.tile_type != 'MOUNTAIN']
        return self.find_closest_target(legion, targets)
        
    def find_closest_border_tile(self, legion):
        border_tiles = []
        for tile in self.get_tiles_owned_by(legion.owner):
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                neighbor = self.get_tile(tile.x+dx, tile.y+dy)
                if neighbor and neighbor.owner != legion.owner and neighbor.tile_type != 'MOUNTAIN':
                    border_tiles.append(tile)
                    break
        return self.find_closest_target(legion, border_tiles)

    def find_closest_unoccupied_enemy_tile(self, legion):
        targets = [t for r in self.grid for t in r if t.owner and t.owner != legion.owner and not self.get_legion_at(t.x, t.y)]
        return self.find_closest_target(legion, targets)

    def find_weakest_kingdom(self, perspective_kingdom):
        weakest, min_score = None, float('inf')
        for k in self.kingdoms:
            if k != perspective_kingdom and not k.is_eliminated:
                score = len(self.get_legions_of(k)) + k.gold / 5
                if score < min_score: min_score, weakest = score, k
        return weakest

    def get_average_enemy_legion_count(self, perspective_kingdom):
        counts = [len(self.get_legions_of(k)) for k in self.kingdoms if k != perspective_kingdom and not k.is_eliminated]
        return sum(counts) / len(counts) if counts else 0
        
    def check_azure_spoils(self, azure_kingdom):
        gold_gain = 0
        my_border_coords = set()
        for tile in self.get_tiles_owned_by(azure_kingdom):
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]: my_border_coords.add((tile.x+dx, tile.y+dy))
        for event in self.combat_events_this_turn:
            if event['attacker'] != azure_kingdom and event['defender'] != azure_kingdom and event['location'] in my_border_coords:
                gold_gain += 2
        return gold_gain

if __name__ == "__main__":
    game = GameBoard(MAP_LAYOUT)
    game.setup_game()
    game.run_simulation()