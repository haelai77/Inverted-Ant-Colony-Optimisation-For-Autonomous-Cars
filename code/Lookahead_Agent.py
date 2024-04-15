import random
import numpy as np
import numpy.typing as npt
from numpy.random import choice
from collections import defaultdict, deque
from math import ceil
import random

class Lookahead_Agent:
    def __init__(self, src, grid=None, ID=None, pheromone = 0, alpha = 5, decay=0.9, spread_pct=0.5, p_dropoff = 0, p_weight = 1, d_weight = 1, move_buffer=[], signalling_toggle = False, detouring=False) -> None:
        self.pheromone = pheromone
        self.delay = 0
        self.alpha = alpha
        self.decay = decay
        self.spread_pct = spread_pct
        self.p_dropoff = p_dropoff
        self.signalling_toggle = signalling_toggle
        self.detouring = detouring
        self.detour_taken = 0
        if ID != "tracker" and grid.test: print(f"detouring: {self.detouring}, alpha:{alpha}, singalling:{self.signalling_toggle}")

        # move buffer for executive moves where agent doesn't get to choose
        self.move_buffer = deque(move_buffer)
        self.p_weight = p_weight
        self.d_weight = d_weight

        # grid related attributes
        self.src: tuple = src[:2] # starting coordinates
        self.dst: tuple = None # ending coordinates
        self.dst_side = None # NOTE used for determining whether a detour has been taken or not

        self.grid = grid # grid object
        self.grid_coord = self.src 
        self.grid.tracker[self.grid_coord] = self
    
        self._init_dst() # randomly assigns a possible destination

        # agent attributes
        self.ID = ID 

        self.direction = self.grid.grid[self.src] # direction of current cell
        self.prev_direction = self.direction

        # # the number of possible moves to move in each direction
        self.detour_directions = []

        # dummy settings
        if self.ID == "DUMMY": 
            self.alpha = 0
        self.pause_chance = 2/10
        self.pause_length = 10
        
        # how the grid coordinate is updated when travelling in each of these directions
        self.cardinal_move = {
            "n": (-1,  0),
            "s": ( 1,  0),
            "e": ( 0,  1),
            "w": ( 0, -1)}
        
        # holds the possible move at each junction
        self.intercard_move = {"se", "sw", "ne", "nw"}
        
        # for checking diagonal cell when entering junction
        self.diag_check = {
            "n": (-1,  1),
            "s": ( 1, -1),
            "e": ( 1,  1),
            "w": (-1, -1)}

        # for calculating relative cell to branch out from and also buffering moves
        self.root_cell = {
            "nww" : ( 0,  0, "w"), # ""
            "nwn" : (-1,  0, "nn"), # "n"
            "nwe" : (-1,  1, "nee"), # "ne"
            "nws" : ( 0,  1, "ness"), # "e"

            "sew" : ( 1, -1, "sww"), # "sw"
            "sen" : ( 0, -1, "swnn"), # "w"
            "see" : ( 0,  0, "e"), # ""
            "ses" : ( 1,  0, "ss"), # "s"

            "sww" : ( 0, -1, "ww"), # "w",
            "swn" : (-1, -1, "wnn"), # "nw",
            "swe" : (-1,  0, "wnee"), # "n",
            "sws" : ( 0,  0, "s"), # "",

            "new" : ( 1,  0, "esww"), # "s",
            "nen" : ( 0,  0, "n"), # "",
            "nee" : ( 0,  1, "ee"), # "e",
            "nes" : ( 1,  1, "ess")} # "se"
     
        self._init_detour_directions(self.src, self.dst) # calculates the moves required to get to destination

    def _init_dst(self):
        '''finds suitable destination and sets current direction'''
        selected = False
        while not selected:
            dst_choice = random.choice(self.grid.exits) # selects random destination  
            if self.src[0] != dst_choice[0] and self.src[1] != dst_choice[1]: # set destination if y and x are not the same
                selected = True
                self.dst = dst_choice[:2]
                self.dst_side = dst_choice[2]

    def _init_detour_directions(self, src, dst):
        '''sets up moveset and possible intercardinal directions'''
        moves = np.subtract(src, dst)
        self.detour_directions = []
        if moves[0] <= 0: # if y diff is neg we go south else north
            self.detour_directions.append("n")
        if moves[0] >= 0:
            self.detour_directions.append("s")
        if moves[1] <= 0: # if x is negative go east else go west
            self.detour_directions.append("w")
        if moves[1] >= 0:
            self.detour_directions.append("e")
##############################################################
    def spread_helper_1(self):
        '''helper function that looks directly behind agent (one direction)'''
        spread_counter = 0 # counts how far away the cell the agent is checking
        pheromone_spread = self.pheromone * self.spread_pct 

        next_check = np.subtract(self.grid_coord, self.cardinal_move[self.direction]) # only need to subtract
        while True:
            spread_counter += 1
            if not (0 <= next_check[0] <= self.grid.CELLS_IN_HEIGHT-1 and 0 <= next_check[1] <= self.grid.CELLS_IN_WIDTH-1): # if not within bounds
                self.pheromone = max(0, self.pheromone - pheromone_spread) # avoids any floating point error going negative
                return []
            else:
                cell = self.grid.tracker[next_check[0], next_check[1]]
                if cell:
                    self.pheromone = max(0, self.pheromone - pheromone_spread) # decreases agent's pheromone pool
                    return [(cell, pheromone_spread * (self.p_dropoff ** spread_counter))] # return agent behind and pheromone it needs to update
                next_check = np.subtract(next_check, self.cardinal_move[self.direction])

    def spread_helper_2(self):
        '''function that helps spread pheromone in 2 directions when at junction i.e. if you are at a NE cell you can spread backwards and west wards as those 2 directions can arrive onto the NE cell'''
        pheromone_spread = self.pheromone * self.spread_pct 
        
        spread_counter = 0 # counts how far away the cell the agent is checking
        next_check = [np.subtract(self.grid_coord, self.cardinal_move[direction]) for direction in self.direction] # next cells to check in each direction
        agents_found = []
        found_flags = [0] * 2

        while not (found_flags[0] and found_flags[1]):
                spread_counter += 1
                for index, direction in enumerate(self.direction):
                    # out of bounds = set found flag so you don't have to check / do any more adding, makes use of short circuiting so skips comparisons
                    if not found_flags[index] and not (0 <= next_check[index][0] <= self.grid.CELLS_IN_HEIGHT-1 and 0 <= next_check[index][1] <= self.grid.CELLS_IN_WIDTH-1):
                        found_flags[index] = 1 
                    elif not found_flags[index]:
                        # if cell contains an agent add it to the found agents list
                        cell = self.grid.tracker[next_check[index][0], next_check[index][1]]
                        if cell: 
                            agents_found.append((cell, pheromone_spread * (self.p_dropoff ** spread_counter)))
                            found_flags[index] = 1
                        next_check[index] = np.subtract(next_check[index], self.cardinal_move[direction])

        self.pheromone = max(0, self.pheromone - pheromone_spread)
        return agents_found

    def spread_pheromone(self) -> tuple[int]:
        '''returns list of tuple/iterator of (agent, pheromone update value)'''
        # straight road case: you just look in opposite to direction of travel
        if self.direction in self.cardinal_move:
            return self.spread_helper_1()
        
        # junction cell case: you need to spread out in 2 directions, backwards to direction fo travel and opposite to the possible turning direction
        elif self.direction in self.intercard_move:
            return self.spread_helper_2()
##############################################################
    def buffer_moves(self, pheromone, endpoint, coord):
        '''buffers junction moves and returns first initial move'''
        _, direction = pheromone
        current_cell = self.grid.grid[tuple(coord)]
        junc_moves = self.root_cell[f"{current_cell}{direction}"][2]
        # buffer junction moves
        self.move_buffer.extend(junc_moves)
        if endpoint:
            # need to calculate new move set as well
            self._init_detour_directions(src=endpoint, dst=self.dst) # calculates as if you are at the next junction of detour

    def search_pheromones(self, coord):
        '''finds a agents on out-roads of current junction, guaranteed to not return agents on exit roads'''
        pheromones = [] # [ (pheromone_found, direction) ]
        curr_junc_cell = self.grid.grid[tuple(coord)]

        best_options = [] #if there is and option with no pheromone and no detouring possible

        # check in all 4 directions
        for direction in "nsew":
            if (not self.detouring) and direction in self.detour_directions: # skip if detour and alpha is zero
                continue

            branch_cell = coord # cell to branch from when checking in each out-road from a junction
            branch_cell = np.add(coord, self.root_cell[f"{curr_junc_cell}{direction}"][:2])
            road_len = np.multiply(self.cardinal_move[direction], self.grid.BLOCK_SIZE)
            exit_check = np.add(branch_cell, road_len)

            # we will always take exit if at exit junction
            if self.dst == tuple(exit_check):
                current_cell = self.grid.grid[tuple(coord)]
                junc_move = self.root_cell[f"{current_cell}{direction}"][2]
                self.move_buffer.extend(junc_move)
                self.move_buffer.extend(direction * self.grid.BLOCK_SIZE)
                return False
            # if direction is going to lead to the wrong exit skip
            elif exit_check[0] in {0, self.grid.CELLS_IN_HEIGHT-1} or exit_check[1] in {0,self.grid.CELLS_IN_WIDTH-1}:
                continue
            else: # if not incorrect or correct exit search for agent
                found_flag = False
                while not found_flag:
                    branch_cell = np.add(branch_cell, self.cardinal_move[direction])
                    # if out of bounds set found to true
                    if not (0 <= branch_cell[0] <= self.grid.CELLS_IN_HEIGHT-1 and 0 <= branch_cell[1] <= self.grid.CELLS_IN_WIDTH-1):
                        #note: takes best path i.e. no pheromones and no detouring
                        # if direction not in self.detour_directions: # takes best option in event detouring is on
                        #     best_options.append((0, direction))
                        pheromones.append((0, direction))
                        found_flag = True
                    # if agent found in direction store it and set found to true
                    elif self.grid.tracker[tuple(branch_cell)]:
                        pheromones.append((self.grid.tracker[tuple(branch_cell)].pheromone, direction))
                        found_flag = True
        if best_options:
            return best_options
        return pheromones
        
    def phero_dist_choice(self, coord): # OPTIMISE
        '''returns immediate move and stores rest in move buffer'''
        extra_dist = {
            "n" : (-int(self.grid_coord[1] < self.dst[1]), 0),
            "s" : (int(self.grid_coord[1] > self.dst[1]), 0),
            "e" : (0, int(self.grid_coord[0] < self.dst[0])),
            "w" : (0, -int(self.grid_coord[0] > self.dst[0]))}

        pheromones = self.search_pheromones(coord) # [ (pheromone, direction) ]
        if not pheromones:
            return
        endpoints = []
        weights = []
        distances = []

        # NOTE moves are now soley determined based on pheromone and distance at junction
        for p_val, direction in pheromones:
            current_cell = self.grid.grid[tuple(coord)]
            
            branch_start = np.add(coord, self.root_cell[f"{current_cell}{direction}"][:2])
            branch_endpoint = np.sum([branch_start, np.multiply(self.cardinal_move[direction], self.grid.BLOCK_SIZE+1), extra_dist[direction]], axis = 0) # coordinate to calculate new distance from (branch_cell + block size + extra distance due to right turn)

            distance = np.sum(np.add(np.abs(np.subtract(branch_endpoint, self.dst)), extra_dist[direction])) # manhattan distance between move endpoint and destination
            distance += (len(self.root_cell[f"{current_cell}{direction}"][2]) - 1 ) # distance required to move in curent junction to reach cell you branch out from taking into account uturn at endpoint

            endpoints.append(tuple(branch_endpoint)) 
            distances.append(distance)

            lin_comb_p_d = ((self.alpha != 0) * self.p_weight * p_val) + (self.d_weight * distance) # if alpha is zero then no pheromones, if detouring is zero then no distance
            power = int((self.alpha == 0) + (self.alpha != 0)*self.alpha)
            weights.append( (1 / int(1 + (lin_comb_p_d))**power) ) # calculate weight as before in Agent.py
        # choose move based on probabilities
        sum_of_weights = np.sum(weights)
        probabilities = [weight/sum_of_weights for weight in weights]

        move_idx = choice(len(distances), p=probabilities) # index

        if self.grid.test:
            probabilities = [round(prob, 3) for prob in probabilities]
            print(list(zip(probabilities, pheromones, distances)), self.detour_directions)
        
        if pheromones[move_idx][1] in self.detour_directions:
            self.detour_taken += 1

        # calculate new move set and buffer required moves
        self.buffer_moves(pheromones[move_idx], endpoints[move_idx], coord)
##############################################################
    def possible_move(self, move_result) ->  bool:
        '''
        checks if move is good and updates location in tracking grid
        -> returning false is a good thing i.e. the move is possible
        '''
        next_cell = self.grid.tracker[move_result[0], move_result[1]]
        # if about to enter junction check next cell empty
        if self.direction in self.cardinal_move and self.grid.grid[move_result[0], move_result[1]] in self.intercard_move and not next_cell:
            diag = np.add(self.diag_check[self.direction], self.grid_coord)
            diag_cell = self.grid.tracker[diag[0], diag[1]]

            # if cell to right of travel isn't empty
            if not diag_cell or (self.signalling_toggle and not tuple(np.add(diag_cell.grid_coord, self.cardinal_move[diag_cell.move_buffer[0]])) == tuple(move_result)):
                self.grid.tracker[self.grid_coord[0], self.grid_coord[1]] = None
                self.grid.tracker[move_result[0], move_result[1]] = self
                return False
            
        elif not next_cell: # next cell is empty
            self.grid.tracker[self.grid_coord[0], self.grid_coord[1]] = None
            self.grid.tracker[move_result[0], move_result[1]] = self
            return False
        return True
##############################################################

    def update_attributes(self, move_choice):
        '''updates grid coordinate in tracker and current direciton of travel, optionally decrements item in moveset if buffer move not selected'''
        if move_choice == "PAUSE":
            return

        self.grid_coord = np.add(self.grid_coord, self.cardinal_move[move_choice]) # update grid coordinate
        self.prev_direction = self.direction
        self.direction = self.grid.grid[self.grid_coord[0], self.grid_coord[1]] # update direction
    
    def move(self):
        if self.ID == "tracker":
            return 1

        self.pheromone = self.pheromone * self.decay

        ###############################################
        # case 1: if destination has been reached
        if self.dst == tuple(self.grid_coord):
            self.grid.tracker[self.grid_coord[0], self.grid_coord[1]] = None
            return False
        ###############################################
        # # case 2: move on executive buffer
        elif self.move_buffer:
            pass
        ###############################################
        # case 4: you're at a junction and need to compare 4 directions, 2 of which will be detours
        # elif self.direction in self.intercard_move and self.prev_direction in self.cardinal_move:
        elif self.direction in self.cardinal_move and self.grid.grid[tuple(np.add(self.grid_coord, self.cardinal_move[self.direction]))] in self.intercard_move:
            
            #if dummy have a chance for pausing
            if self.ID == "DUMMY" and random.random() <= self.pause_chance:
                self.move_buffer.extend(["PAUSE"] * self.pause_length)

            #still buffer moves for after pause
            self.move_buffer.append(self.direction)
            self.phero_dist_choice(np.add(self.grid_coord, self.cardinal_move[self.direction])) # this buffers neccessary moves
        ###############################################
        # case 3: straight road -> move ahead if possible
        elif self.direction in self.cardinal_move: # if cardinal direction and possible to move
            self.move_buffer.append(self.direction)

        else:
            if len(self.move_buffer) == 0:
                raise Exception("no choices oh no")
        ###############################################
        # possible move check
        if self.move_buffer[0] != "PAUSE" and self.possible_move(np.add(self.grid_coord, self.cardinal_move[self.move_buffer[0]])):
            self.delay += 1
            self.pheromone += 1
            return True
        else:
            move_choice = self.move_buffer.popleft()
        ###############################################
        self.update_attributes(move_choice)
        return True
    