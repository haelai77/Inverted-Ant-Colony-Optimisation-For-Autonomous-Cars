import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import pygame as pg
import numpy as np
from Agent import Agent
from Lookahead_Agent import Lookahead_Agent
from Grid import Grid
import random
import argparse

import math
from itertools import combinations

GREY = (128, 128, 128)
WHITE = (255, 255, 255)

GREEN = (10, 196, 0)
RED =  (255, 0, 0)
ORANGE = (252, 127, 3)
BLUE = (30,144,255)

TEMP_AGENT_COLOUR = (242, 0, 255)



class simulation:

    def split_quadrant_helper(self, tracker):

        quadrants = []

        quadrants.append(tracker[0:33, 0:33]) #00
        quadrants.append(tracker[0:33, 33:67]) #01
        quadrants.append(tracker[0:33, 67:100]) # 02

        quadrants.append(tracker[33:67, 0:33]) # 03
        quadrants.append(tracker[33:67, 33:67]) # 04
        quadrants.append(tracker[33:67, 67:100]) # 05

        quadrants.append(tracker[67:100, 0:33]) # 06
        quadrants.append(tracker[67:100, 33:67]) # 07
        quadrants.append(tracker[67:100, 67:1000]) # 08

        return quadrants
    
    def agent_coords(self, quadrant):
        coords = []

        for i in range(len(quadrant)):
            for j in range(len(quadrant[0])):
                if quadrant[i][j] is not None:
                    coords.append((i,j))
        return coords
    
    def dist(self, p1,p2):
        (x1, y1), (x2, y2) = p1, p2
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def calc_avg_dist(self, coords_list):
        distances = []
        # print(list(combinations(coords_list, 2)),)
        for combo in combinations(coords_list, 2):
            p1, p2 = combo
            distances.append(self.dist(p1, p2))
        return sum(distances)/len(distances)


    def nearest_neighoburs_check(self, tracker):
        """returns the average distance between all agents within each quadrant of the environemnt split into 9 sections"""
        quadrants = self.split_quadrant_helper(tracker)
        results = []
        number_in_quadrant = []

        for quadrant in quadrants:
            agent_coordianates = self.agent_coords(quadrant)
            number_in_quadrant.append(len(agent_coordianates))
            average_dist = self.calc_avg_dist(agent_coordianates)
            results.append(average_dist)

        print("num agents in quadrants:", number_in_quadrant)
        print("avg dist between agents:", results)
        return 


    def isfinished(self, agents):
        finished = []
        agents_new = []

        for agent in agents:
            if agent.move():
                agents_new.append(agent)
            else:
                finished.append(agent)
        
        random.shuffle(agents_new)
        return finished, agents_new

    def env_loop(self,
                p_dropoff = 0,
                p_weight=1, 
                d_weight=1, 
                spread_pct=0.5, 
                lookahead=False, 
                detouring=False, 
                signalling_toggle = False,
                roads=5,
                vis=False, 
                t=0, 
                t_max=20000, 
                round_density=2.3, 
                alpha=0, 
                speed=100, 
                test=False, 
                GA=False,
                dummy=False,
                
                cong=False) -> None:
        
        '''runs simulation'''
        #initial grid
        grid = Grid(num_roads_on_axis = roads)

        # initial agents
        agents = grid.generate_agents(round_density=round_density, 
                                    alpha=alpha, 
                                    p_dropoff=p_dropoff,
                                    p_weight=p_weight,
                                    d_weight=d_weight,
                                    spread_pct=spread_pct,
                                    lookahead=lookahead,
                                    detouring=detouring,
                                    signalling_toggle=signalling_toggle,
                                    dummy=dummy,
                                    test=test)
        #### for GA ####
        end_counter = 0
        t_save = None
        delay = []
        num_finished = []
        ################

        if vis:
            print(f"p_drop: {p_dropoff}, p_weight:{p_weight}, d_weight:{d_weight}, lookahead:{lookahead}, signalling:{signalling_toggle}, detouring:{detouring}")
            pg.init() # initialises imported pygame modules
            screen = pg.display.set_mode(grid.WINDOW_SIZE, pg.RESIZABLE)
            pg.display.set_caption("simple traffic simulation") # set window title
            clock = pg.time.Clock() # Used to manage how fast the screen updates

            # updates agents on screen
            move_event = pg.USEREVENT
            pg.time.set_timer(move_event, speed)
            max_pheromone = 0
            max_delay = 0
            orang_thresh = 9999
            red_thresh = 9999

            # -------- Main Game Loop ----------- #
            pause = False
            while t != t_max:

                pg.display.set_caption(f'[t:{t}] [max_p = {round(max_pheromone, 2)}] [max delay = {max_delay}] [density = {round_density}] [alpha = {alpha}] [spread_decay = {p_dropoff}] [detouring: {detouring}] [signalling: {signalling_toggle}]')
                # HANDLE EVENTS
                for event in pg.event.get():
                    # pause
                    if event.type == pg.KEYDOWN and event.key == pg.K_p:
                        pause = not pause
                    
                    elif event.type == move_event and not pause:
                        update_ph_list = []
                        _, agents = self.isfinished(agents=agents) # removes ones that have reached their destination 
                        # # calculate pheromone increase
                        for agent in agents:
                            if agent.ID =="tracker": continue
                            update_ph_list.extend(agent.spread_pheromone())
                        # apply pheromone changes
                        for agent, update_val in update_ph_list:
                            agent.pheromone += update_val

                        # # add more agents
                        if not test: agents.extend(grid.generate_agents(round_density=round_density, 
                                                                        alpha=alpha, 
                                                                        p_dropoff=p_dropoff,
                                                                        p_weight=p_weight,
                                                                        d_weight=d_weight,
                                                                        spread_pct=spread_pct,
                                                                        lookahead=lookahead, 
                                                                        detouring=detouring, 
                                                                        signalling_toggle=signalling_toggle,
                                                                        dummy=dummy))

                        t += 1
                    elif event.type == pg.MOUSEBUTTONDOWN:
                        pos = pg.mouse.get_pos()
                        column = pos[0] // (grid.CELL_SIZE + grid.MARGIN)
                        row = pos[1] // (grid.CELL_SIZE + grid.MARGIN)
                        print("Click ", pos, "Grid coordinates: ", row, column)
                    elif event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                        pg.quit()
                    elif event.type == pg.QUIT:  # If user clicked close
                        pg.quit()

                screen.fill(GREY)
                
                # draw grid
                for row in range(grid.CELLS_IN_WIDTH):
                    for col in range(grid.CELLS_IN_HEIGHT):

                        colour = GREY
                        if grid.grid[row][col] in {"n","s","e", "w", "ne", "se", "nw", "sw"}: colour = WHITE # junction

                        # draw cells
                        pg.draw.rect(screen,
                                    colour,
                                    [(grid.MARGIN + grid.CELL_SIZE) * col + grid.MARGIN, # top y coord 
                                    (grid.MARGIN + grid.CELL_SIZE) * row + grid.MARGIN, # top x left
                                    grid.CELL_SIZE,   # width of rect
                                    grid.CELL_SIZE])  # height of rect
                # draw agents
                for agent in agents:
                    if agent.delay > max_delay:
                        max_delay = agent.delay
                    if max_pheromone < agent.pheromone:
                        max_pheromone = agent.pheromone
                        orang_thresh = 4#0.333 * max_pheromone
                        red_thresh = 6# * max_pheromone

                    row, col = agent.grid_coord
                    srow, scol = agent.src
                    drow, dcol = agent.dst
                    colour = GREEN
                    if red_thresh > agent.pheromone >= orang_thresh:
                        colour = ORANGE
                    elif agent.pheromone >= red_thresh:
                        colour = RED
                    if type(agent.ID) == str:
                        colour=TEMP_AGENT_COLOUR

                    if type(agent.ID) == int:
                        pg.draw.rect(screen, # entrance
                                    BLUE, 
                                    [(grid.MARGIN + grid.CELL_SIZE) * scol + grid.MARGIN, # top y coord 
                                    (grid.MARGIN + grid.CELL_SIZE) * srow + grid.MARGIN, # top x left
                                    grid.CELL_SIZE,   # width of rect
                                    grid.CELL_SIZE])  # height of rect
                        
                        pg.draw.rect(screen, # exit
                                    RED, 
                                    [(grid.MARGIN + grid.CELL_SIZE) * dcol + grid.MARGIN, # top y coord 
                                    (grid.MARGIN + grid.CELL_SIZE) * drow + grid.MARGIN, # top x left
                                    grid.CELL_SIZE,   # width of rect
                                    grid.CELL_SIZE])  # height of rect

                    pg.draw.rect(screen, # agent
                                colour, 
                                [(grid.MARGIN + grid.CELL_SIZE) * col + grid.MARGIN, # top y coord 
                                (grid.MARGIN + grid.CELL_SIZE) * row + grid.MARGIN, # top x left
                                grid.CELL_SIZE,   # width of rect
                                grid.CELL_SIZE])  # height of rect
                
                clock.tick(120) # fps
                pg.display.flip() # draws new frame
            pg.quit()

        else:
            while t != t_max:
                update_ph_list = []
                finished, agents = self.isfinished(agents=agents)
                num_of_finished = len(finished)

                # calculate pheromone increase
                for agent in agents:
                    if agent.ID != "DUMMY" or agent.ID != "tracker":
                        update_ph_list.extend(agent.spread_pheromone())

                # apply pheromone changes
                for agent, update_val in update_ph_list:
                    agent.pheromone += update_val
                    
                # add more agents
                agents.extend(grid.generate_agents(round_density=round_density, 
                                                alpha=alpha, 
                                                p_dropoff=p_dropoff,
                                                p_weight=p_weight,
                                                d_weight=d_weight,
                                                spread_pct=spread_pct,
                                                lookahead=lookahead, 
                                                detouring=detouring, 
                                                signalling_toggle=signalling_toggle,
                                                dummy=dummy))
                t += 1

                # not agents have finished in 500 time steps
                if end_counter >= 500:
                    print("gridlocked", t_save)
                    break
                
                if finished:
                    end_counter = 0
                    min_delay = min(agent.delay for agent in finished)
                    max_delay = max(agent.delay for agent in finished)
                    mean_delay = np.mean([agent.delay for agent in finished])
                    mean_detours = np.mean([agent.detour_taken for agent in finished]) if detouring else 0

                    if not GA and not cong:
                        print(min_delay, max_delay, mean_delay, num_of_finished)
                    elif t >= (t_max-1000):
                        num_finished.append(len(finished))
                        delay.append(mean_delay)
                        
                else:
                    t_save = t
                    end_counter += 1
                    if not GA and not cong:
                        print(0, 0, 0, num_of_finished)
                    elif t >= (t_max-1000):
                        num_finished.append(0)
                        delay.append(0)

        if GA:
            # if the number of agents that have finished in the last 1000 is less than 
            filtered_delay = []

            # if no agents have finished then don't consider the delay
            for i, num_fin in enumerate(num_finished):
                if num_fin != 0:
                    filtered_delay.append(delay[i])

            return sum(filtered_delay)/len(filtered_delay) + (t_max - t_save + 1)
        
        if cong:
            self.nearest_neighoburs_check(grid.tracker)