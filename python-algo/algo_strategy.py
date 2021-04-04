import gamelib
import random
import math
from sys import maxsize
import json


"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""


class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write("Random seed: {}".format(seed))

    def on_game_start(self, config):
        """
        Read in config and perform any initial setup here
        """
        gamelib.debug_write("Configuring your custom algo strategy...")
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP 
        
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0

        global HOME_FIELD, OPP_SIDE, SCORE_LOC, DEPLOY_LOC, mp_threshold
        HOME_FIELD = self.get_my_grid()
        OPP_SIDE =  self.get_opp_grid()
        SCORE_LOC = self.get_scoring_locs()
        DEPLOY_LOC = self.get_deploy_loc()
        self.is_attacking = False
        self.attacking_round_start = -1
        self.attacking_right = False
        mp_threshold = 8

        # This is a good place to do initial setup
        self.scored_on_locations = []
        self.damaged_locs = []
        self.REINFORCE_MID = False

        self.enemy_units = [[], [], [], [], [], [], [], []]
        self.BEGIN = True
        self.DEMOLISHER = False
        self.last_demolisher_run = 0
        # Used for the support logic
        self.support_locations = []

        for i in range(14, 11, -1):
            for j in range(5, 2, -1):
                self.support_locations.append([i, j])
        
        self.built_supports = []
        self.upgraded_supports = []

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write(
            "Performing turn {} of your custom algo strategy".format(
                game_state.turn_number
            )
        )
        game_state.suppress_warnings(
            True
        )  # Comment or remove this line to enable warnings.
        resources = game_state.get_resources()
        self.SP = resources[0]
        self.MP = resources[1]
        self.damaged_locs, self.average_x = self.get_damaged_units(
            game_state.game_map
        )
        self.detect_demolishers(game_state)

        if self.is_attacking == True: # one before the attacking stage, we want to build walls
            if game_state.turn_number == self.attacking_round_start - 1:
                game_state.attempt_spawn(WALL, [[10,7],[11,7],[12,7],[13,7],[14,7],[15,7],[16,7]])
            if game_state.turn_number == self.attacking_round_start + 1:
                self.is_attacking = False
                self.attacking_right = False
                game_state.attempt_remove([[10,7],[11,7],[12,7],[13,7],[14,7],[15,7],[16,7]])
    
        if self.is_attacking == False:
            self.build_defences(game_state)
        
        # defensive scheme + support
        self.build_support(game_state)

        self.refund_damaged_units(game_state)
                
        if self.is_attacking:
            if game_state.turn_number == self.attacking_round_start:
                if self.attacking_right:
                    game_state.attempt_spawn(SCOUT, [8,5], 12)
                    game_state.attempt_spawn(SCOUT, [13,0], int(self.MP)-12)
                else:
                    game_state.attempt_spawn(SCOUT, [19,5], 12)
                    game_state.attempt_spawn(SCOUT, [14,0], int(self.MP)-12)
        else:
            mp_threshold = self.adjust_attack_mp_thresh(game_state.turn_number)
            if self.MP >= mp_threshold:
                deploy_possible_arr = []
                for x in DEPLOY_LOC:
                    if game_state.contains_stationary_unit(x) == False:
                        deploy_possible_arr += [x]
                least_damage_res = self.least_damage_spawn_location(game_state, deploy_possible_arr)
                least_damage_loc = least_damage_res[0]
                least_damage_num = least_damage_res[1]
                # deploy_possible_arr.remove(least_damage_loc)
                # second_least_dmg_res = self.least_damage_spawn_location(game_state, deploy_possible_arr)
                # second_least_damage_loc = second_least_dmg_res[0]
                # second_least_damage_num = second_least_dmg_res[1]
                if least_damage_num > 260: # then they probably have good defense in general
                    # go for the corners
                    # but first, do they have walls on the edges?
                    self.attacking_round_start = game_state.turn_number+4
                    self.is_attacking = True
                    left_corner_wall =  game_state.contains_stationary_unit([0, 14])
                    right_corner_wall = game_state.contains_stationary_unit([27, 14])
                    is_blocked = False
                    go_right = False
                    if left_corner_wall and right_corner_wall:
                        is_blocked = True
                    elif left_corner_wall:
                        go_right = True
                    if go_right:
                        self.attacking_right = True
                        # game_state.attempt_remove([[26,13],[27,13],[26,12],[25,12]])
                        game_state.attempt_remove([[26,13],[27,13]])
                    else:
                        # game_state.attempt_remove([[0,13],[1,13],[1,12],[2,12]])
                        game_state.attempt_remove([[0,13],[1,13]])
                # if deploy_targ is on left side, spawn remaining a little behind
                # vice versa
                else:
                    first_stack_num = 8
                    if self.is_attacking == True:
                        first_stack_num = 12
                    game_state.attempt_spawn(SCOUT, least_damage_loc, first_stack_num)
                    remaining_mp = int(self.MP) - 8
                    second_loc = [0, 0]
                    if least_damage_loc[0] > 13: # then it's on the right side
                        second_loc[0] = least_damage_loc[0] - 2
                        second_loc[1] = least_damage_loc[1] - 2
                    else:
                        second_loc[0] = least_damage_loc[0] + 2
                        second_loc[1] = least_damage_loc[1] - 2
                    game_state.attempt_spawn(SCOUT, second_loc, remaining_mp)
        game_state.submit_turn()

    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """
    # gets all locations on my side of the map
    def get_my_grid(self):
        """
        Gets all coordinates on player's side
        """
        arr = []
        for y in range(13, -1, -1):
            for x in range(13-y, 15+y):
                arr += [[x, y]]
        return arr

    # gets all locations on opp side of the map
    def get_opp_grid(self):
        arr = []
        for y in range(14,28):
            offset = y-14
            for x in range(offset, 28-offset):
                arr += [[x,y]]
        return arr
    
    # run at start of round or keep as global variables
    # gets all edge points that allows you to score on the enemy side
    def get_scoring_locs(self):
        arr = []
        for x in range(0,14):
                arr += [[x, 14+x], [27-x, 14+x]]
        return arr

    # gets all edge points on user side that allows you to deploy attacking units on
    def get_deploy_loc(self):
        arr = []
        for x in range(0,14):
                arr += [[x, 13-x], [27-x, 13-x]]
        return arr

    def get_damaged_units(self, game_map):
        """
        gets the locations of all damaged units on player's side
        :input game_map: GameMap object
        """

        # TODO: debug
        my_units = []
        for coords in HOME_FIELD:
            units_at_location = game_map[coords[0], coords[1]]
            my_units += units_at_location
        
        damaged_list = []
        average_x = 0
        # check if each unit is < 75% health
        for unit in my_units:
            if (unit.stationary and unit.max_health * 0.75 > unit.health and
                    unit.pending_removal is False):
                damaged_list.append([unit.x, unit.y])
                average_x += unit.x
        if len(damaged_list) > 0:
            average_x /= len(damaged_list)
        
        return damaged_list, average_x
    
    def detect_demolishers(self, game_state):
        """
        decide if we need to send in interceptors
        modifies the interceptor flag accordingly
        """
        gamelib.util.debug_write(self.enemy_units)

        enemy_demolishers = self.enemy_units[4]
        enemy_resources = game_state.get_resources(1)
        enemy_MP = enemy_resources[1]

        if len(enemy_demolishers) > 0:
            self.last_demolisher_run = 0
            self.DEMOLISHER = True
        
        if self.DEMOLISHER is False:
            return
        
        # find random interceptor location
        possible_starts = [
            [16, 2],
            [14, 0],
            [8, 5],
            [6, 7]
        ]
        good_choice = None
        while good_choice is None:
            possible = random.choice(possible_starts)
            last_spot = game_state.find_path_to_edge(possible)[-1]
            if last_spot not in HOME_FIELD:
                good_choice = possible

        if self.last_demolisher_run > 2 or enemy_MP > 5:
            game_state.attempt_spawn(INTERCEPTOR, good_choice)




    def spawn_and_update(self, game_state, unit_type, locations):
        """
        Wrapper function that attempts spawning the units and then 
        updates the SP variable
        """
        return_value = game_state.attempt_spawn(unit_type, locations)
        resources = game_state.get_resources()
        self.SP = resources[0]
        return return_value

    def upgrade_and_update(self, game_state, locations):
        """
        Wrapper function that attempts upgrading the units and then 
        updates the SP variable
        """
        return_value = game_state.attempt_upgrade(locations)
        resources = game_state.get_resources()
        self.SP = resources[0]
        return return_value

    def build_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where
        enemy demolishers can attack them.
        """
        
        # Turn 0 master plan
        # Place turrets that attack enemy units
        turret_locations_corner = [[23, 11], [4, 11]]
        turret_locations_mid = [[9, 7], [17, 7]]
        turret_locations = turret_locations_corner + turret_locations_mid
        self.spawn_and_update(game_state, TURRET, turret_locations_corner +
                              turret_locations_mid)

        # upgrade turrets after they attack
        self.upgrade_and_update(game_state, turret_locations)

        wall_locations = []

        # front line walls
        for i in [0, 1, 2, 25, 26, 27]:
            wall_locations.append([i, 13])

        # protect the turrets
        for turret in turret_locations:
            wall_locations.append([turret[0], turret[1] + 1])

        self.spawn_and_update(game_state, WALL, wall_locations)
        
        extra_front_walls = []
        # reinforced front line, which side to attempt to add
        if game_state.turn_number > 1:
            extra_front_walls = self.reinforce_front(game_state)

        # wall upgrade logic
        front_line = wall_locations[:-4] + extra_front_walls
        turret_walls = wall_locations[-4:]
        if game_state.turn_number > 5: # 10 was randomly derived, maybe room for improvement?
            # upgrade frontline walls first
            # upgrade the walls by front turrets
            self.upgrade_and_update(game_state, front_line)
            self.upgrade_and_update(game_state, turret_walls)

        # begin the wings after turn 4
        if game_state.turn_number > 3:
            self.build_wings(game_state)

        # begin reinforcing the mid after turn 4
        if game_state.turn_number > 4:
            self.reinforce_mid(game_state)

    def reinforce_front(self, game_state):
        """
        adds two walls off the front side
        decide if we want reinforce left or right first
        """
        # right_corner = [[24, 13], [23, 13], [26, 12], [25, 12]]
        # left_corner = [[3, 13], [4, 13], [1,12], [2,12]]
        right_corner = [[24, 13], [23, 13]]
        left_corner = [[3, 13], [4, 13]]
        new_locations = []
        
        # if SP is constrained, decide with damaged locations
        if self.SP > 4:
            new_locations = right_corner + left_corner
        else:
            if self.average_x > 13.5:
                new_locations = right_corner + left_corner
            else:
                new_locations = left_corner + right_corner

        self.spawn_and_update(game_state, WALL, new_locations)
        # new_locations = left_corner[:2] + right_corner[:2]
        return new_locations

    def build_wings(self, game_state):
        """
        Logic to build the wing walls
        builds everything if no resource constraints
        else lets focus our efforts ont eh side that needs more help
        """

        left_wing = [
            [5, 11],
            [6, 10],
            [7, 9],
            [8, 8],
            [10, 7]
        ]

        right_wing = [
            [22, 11],
            [21, 10],
            [20, 9],
            [19, 8],
            [18, 8]
        ]

        # if no resource constraint
        if self.SP > 9:
            both_wings = left_wing + right_wing
            self.spawn_and_update(game_state, WALL, both_wings)
        else:
            # check where opponent is breaching
            avg_x = 0
            for breach in self.scored_on_locations:
                avg_x += breach[0]

            if len(self.scored_on_locations) > 0:
                avg_x /= len(self.scored_on_locations)

            if avg_x > 13.5:
                self.spawn_and_update(game_state, WALL, right_wing)
                self.spawn_and_update(game_state, WALL, left_wing)
            else:
                self.spawn_and_update(game_state, WALL, left_wing)
                self.spawn_and_update(game_state, WALL, right_wing)

    def reinforce_mid(self, game_state):
        """
        Adds a line of wall structures in front of the opening
        Probably used for after turn 5
        logic is to just create the walls if possible from left to right

        Logic for mid turrets
        if SP > 10 and health is <=25, build
        """
        
        # build the middle wall
        middle_wall = []
        for i in range(11, 16):
            middle_wall.append([i, 9])
        
        self.spawn_and_update(game_state, WALL, middle_wall)

        # add turrets if resource allows and we are damaged or REINFORCE flag 
        # is on
        if self.REINFORCE_MID or (self.SP > 5 and game_state.my_health <= 25):
            self.REINFORCE_MID = True
            turrets = [[11, 10], [15, 10]]
            walls = [[11, 9], [15, 9]]
            self.spawn_and_update(game_state, TURRET, turrets)
            self.upgrade_and_update(game_state, turrets)
            self.spawn_and_update(game_state, WALL, walls)

    def build_support(self, game_state):
        """
        building the support needed for our offense
        checks for turn number then utilizes what is needed

        Hamlin's notes
        check for the turn number
            - allows us to know when to be upgraded

        """
        # check the number of supports that we have built

        built_number = len(self.built_supports)
        locations = len(self.support_locations)
        
        # support walls
        support_wall_locations = [
            [14, 6],
            [13, 6],
            [12, 6]
        ]
        
        wall_number = built_number if built_number < 9 else 8
        for i in range(wall_number // 3 + 1):
            self.spawn_and_update(game_state, WALL, support_wall_locations[i])

        if built_number < locations: 
            for i in range(built_number, locations):
                test = self.spawn_and_update(game_state, SUPPORT,
                                             self.support_locations[i])
                if test == 0:
                    break
                else:
                    self.built_supports.append(self.support_locations[i])
        else:
            self.built_supports = self.support_locations
            self.spawn_and_update(game_state, SUPPORT, self.support_locations)
        
        # upgrade after
        if len(self.built_supports) > 0:
            self.upgrade_and_update(game_state, self.built_supports)
    
    def refund_damaged_units(self, game_state):
        """
        Removed damaged units
        """
        removed = 0
        if len(self.damaged_locs) > 0:
            game_state.attempt_remove(self.damaged_locs)

        return removed

    # Offensive helper functions
    def adjust_attack_mp_thresh(self, t_n):
        if t_n <= 5:
            return 8
        elif t_n > 5 and t_n <= 10:
            return 13
        elif t_n > 10:
            return 18

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                turrets = game_state.get_attackers(path_location, 1)
                for t in turrets:
                    if t.upgraded == True:
                        damage += 20
                    else:
                        damage += 6
            if game_state.contains_stationary_unit(path[-1]):
                damage += game_state.game_map[path[-1][0], path[-1][1]].health
            damages.append(damage)
        
        # Now just return the location that takes the least damage
        gamelib.debug_write("lowest damage = " + str(min(damages)))
        return [location_options[damages.index(min(damages))], min(damages)]

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called
        hundreds of times per turn and could slow the algo down so avoid putting
        slow code here.  Processing the action frames is complicated so we only
        suggest it if you have time and experience.  Full doc on format of a
        game frame at in json-docs.html in the root of the Starterkit.
        """
        # Read in string as json
        state = json.loads(turn_string)
        
        if self.BEGIN:
            gamelib.util.debug_write(state)
            self.enemy_units = state['p2Units'] 
            self.BEGIN = False

        # Let's record at what position we get scored on
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly,
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0,
            # 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write(
                    "All locations: {}".format(self.scored_on_locations)
                )


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
