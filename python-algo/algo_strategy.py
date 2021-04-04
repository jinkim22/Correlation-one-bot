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

        global HOME_FIELD
        HOME_FIELD = self.get_my_grid()

        # This is a good place to do initial setup
        self.scored_on_locations = []
        self.damaged_locs = []
        self.REINFORCE_MID = False

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
        
        # defensive scheme + support
        self.build_defences(game_state)

        self.build_support(game_state)

        self.refund_damaged_units(game_state)

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
        if game_state.turn_number > 5:
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
        right_corner = [[24, 13], [23, 13]]
        left_corner = [[4, 13], [5, 13]]
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
        if self.REINFORCE_MID or (self.SP > 10 and game_state.my_health <= 25):
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
