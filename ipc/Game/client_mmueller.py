import socket
from enum import Enum
from random import randint
import math
import argparse
import heapq

name = 'client_mmueller'    # name that will be displayed on the server

"""
Der Dijkstra Algorythmus wurde von "http://www.redblobgames.com/pathfinding/a-star/implementation.html"
übernommen und leicht verändert.
"""


class PriorityQueue:
    """
    This is from http://www.redblobgames.com/pathfinding/a-star/implementation.html
    """
    def __init__(self):
        self.elements = []

    def empty(self):
        return len(self.elements) == 0

    def put(self, item, priority):
        self.elements.append((priority, item))
        self.elements.sort(key=lambda tup: tup[0])

    def get(self):
        return heapq.heappop(self.elements)[1]


class FieldType(Enum):
    UNKNOWN = 'U'
    GRASS = 'G'
    CASTLE = 'C'
    FOREST = 'F'
    MOUNTAIN = 'M'
    LAKE = 'L'


class ClientController:
    """
    This is a bot for a competition held at my school. In the game, 2 bots compete against each other and the first
     one to find and take the bomb to the enemies castle wins. The game Area is variable and warps around on the edges
     ((9, 9) neighbours (0, 9)). The bot can move only in one direction and every round the server sends the Bot a
     string representing the area seen by the bot.
    """
    def __init__(self, ip="localhost", port="5050", size="10", verbose=False):
        """
        The Bot gets initialized here and connects to the server.

        :param ip: the ip to connect to
        :param port: the port to connect to
        :param size: the size of the map
        :param verbose: weather or not the bot prints various massages in the commandline
        """
        self.map = []           # internal Map
        self.mapsize = size     # size of the map
        self.xy = [0, 0]        # position
        self.xy_scroll = [0, 0]  # position of the scroll
        self.xy_Fcast = [0, 0]  # position of the enemy castle
        self.g_scroll = False    # got scroll
        self.f_scroll = False    # found scroll
        self.f_Fcast = False    # found enemy castle
        self.turn = 0           # number of turns (total)
        self.last_dir = 0       # last direction we went
        self.verbose = verbose  #

        while len(self.map) < self.mapsize:
            lst = []
            while len(lst) < self.mapsize:
                lst.append(FieldType.UNKNOWN.value)
            self.map.append(lst)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.clientsocket:
            try:
                # Verbindung herstellen (Gegenpart: accept() )
                self.clientsocket.connect((ip, port))
                msg = name
                # Nachricht schicken
                self.clientsocket.send(msg.encode())
                # Antwort empfangen
                data = self.clientsocket.recv(1024).decode()
                if not data or not data == "OK":
                    # Schließen, falls Verbindung geschlossen wurde
                    self.clientsocket.close()

                while self.msg_rec():   # the main loop
                    self.go()

                if self.verbose:
                    print("end")
                self.clientsocket.close()
            except socket.error as serr:
                print("Socket error: " + serr.strerror)

    def addView(self, view):
        """
        The field of view is being added to the internal map.

        :param view: a 2d list, containing all fields
        """
        dist = (len(view)-1)/2  # the viewing distance
        if self.verbose:    # if the bot is in verbose mode, a lot of information is displayed here
            print()
            print("%i ter Zug:" % (self.turn+1))
            print("Sichtweite: %d" % dist)
            print("Position: %i, %i" % (self.xy[0], self.xy[1]))
            gscroll = ""
            if self.g_scroll:
                gscroll = "(got it)"
            if self.f_scroll:
                print("Found Scroll: %i, %i %s" % (self.xy_scroll[0], self.xy_scroll[1], gscroll))
            if self.f_Fcast:
                print("Found Castle: %i, %i" % (self.xy_Fcast[0], self.xy_Fcast[1]))

        for y in range(0, len(view)):
            if self.verbose:
                print(view[y])
            for x in range(0, len(view)):
                ab = self.translate(x, y, dist)
                a = ab[0]   # x position on the real map
                b = ab[1]   # y position on the real map
                if view[y][x].upper() == FieldType.CASTLE.value and a != 0 and b != 0:
                    # if the field type is 'G' and it is not on (0, 0) the bot recognises it as the enemies castle
                    self.f_Fcast = True
                    self.xy_Fcast = [a, b]
                self.map[b][a] = view[y][x].upper()

    def clearView(self):
        """
        Clears the internal map, not really usefull though
        """
        self.map = []
        while len(self.map) < self.mapsize:
            lst = []
            while len(lst) < self.mapsize:
                lst.append(FieldType.UNKNOWN.value)
            self.map.append(lst)

    def dijkstra_search(self, goal):
        """
        This find the most efficient path from the current position to the specified goal
        this has been taken from: http://www.redblobgames.com/pathfinding/a-star/implementation.html
        and modified for my needs. (dont really know how it works tbh)

        :param goal: the destination
        """
        frontier = PriorityQueue()
        frontier.put(tuple(self.xy), 0)
        goal = tuple(goal)
        came_from = {}
        cost_so_far = {}
        came_from[tuple(self.xy)] = None
        cost_so_far[tuple(self.xy)] = 0

        while not frontier.empty():
            current = frontier.get()

            if current == goal:
                break

            for nextN in self.getNeighbours(current):
                nextN = tuple(nextN)
                new_cost = cost_so_far[current] + self.weight(list(current))
                if nextN not in cost_so_far or new_cost < cost_so_far[nextN]:
                    cost_so_far[nextN] = new_cost
                    priority = new_cost
                    frontier.put(nextN, priority)
                    came_from[nextN] = current

        path = ClientController.reconstruct_path(came_from, tuple(self.xy), goal)
        if self.verbose:
            print(path)
        if len(path) == 0:
            if self.f_scroll == False:
                pass
            else:
                self.g_scroll = True
            self.go()
        else:
            neighbours = self.getNeighbours(self.xy)
            for i in range(0, len(neighbours)):
                if neighbours[i] == list(path[0]):
                    self.goStep(str(i))

            return path[0]

    def go(self):
        """
        Deferments what Algorithm to use and where to go to
        """
        if self.f_scroll and not self.g_scroll:
            self.goTo(self.xy_scroll)
        elif self.g_scroll and self.f_Fcast:
            self.goTo(self.xy_Fcast)
        else:
            self.goRandom()

    def goRandom(self):
        """
        This is being called, if the next target is not discovered yet, not really random.
        In the first 3 rounds, it goes to the field with the least weight, after that, it goes to the field with the
        most neighbours(and neighbours of neighbours and ...) that are undiscovered, trying to reveal the whole map.
        """
        if self.turn < 3:
            # this part gets all neighbouring fields and puts them in a PriorityQueue() in order to get the one
            # with the lowest wight
            neig = self.getNeighbours(self.xy)
            if self.turn > 0:
                neig.pop((self.last_dir+2)%len(neig))
            pqueue = PriorityQueue()
            for i in neig:
                pqueue.put(tuple(i), self.weight(i, 5))

            # this takes the step with the least weight and translates it to a number and then goes that direction
            step = pqueue.get()
            neighbours = self.getNeighbours(self.xy)
            for i in range(0, len(neighbours)):
                if neighbours[i] == list(step):
                    self.goStep(str(i))
        else:
            pqueue = PriorityQueue()
            for y in range(0, len(self.map)):
                for x in range(0, len(self.map)):
                    pqueue.put((x, y), self.findUnknown([x, y], 4))

            tmp = pqueue.get()
            if self.verbose:
                print(tmp)
            self.dijkstra_search(tmp)

    def findUnknown(self, xy, level):
        """
        This method finds the field on the map with the most unknown neighbours (recursively)

        :param xy: position of field
        :param level: how many levels to go down (rate of recursion)
        :return: a weight calculated
        """
        neigh = self.getNeighbours(xy)
        u = 1
        if self.map[xy[1]][xy[0]] == FieldType.UNKNOWN.value:
            u -= 1
        for f in neigh:
            if level > 0:
                u += self.findUnknown(f, level-1)/len(self.getNeighbours(f))
        return u

    def goStep(self, step):
        """
        This takes the specified number, translates it to a direction and then sends the server the right command.

        :param step:
        """
        dir = {
            '0': 'up',
            '1': 'right',
            '2': 'down',
            '3': 'left'
        }[step]
        self.last_dir = int(step)
        self.clientsocket.send(dir.encode())
        self.moveX(step)

    def goTo(self, xy):
        """
        This was useful in the past :/

        :param xy: target
        """
        self.dijkstra_search(xy)

    def getNeighbours(self, xy):
        """
        This method returns a list of all neighbouring fields of a specified source field.

        :param xy: the source field
        :return: a list of al neighbouring fields
        """
        lst = []
        xy = list(xy)
        for i in range(0, 2):
            if i == 1:
                a = xy[0] - 1
                b = xy[1] + 1
            else:
                a = xy[0] + 1
                b = xy[1] - 1
            a = self.warp(a)
            b = self.warp(b)
            lst.append([self.warp(xy[0]), b])
            lst.append([a, self.warp(xy[1])])

        return lst

    def getNewFields(self, xy):
        """
        This Method returns how many fields are unknown in the area of the given field.

        :param xy: the field to test
        :return: amount of unknown fields
        """
        i = 0
        lst = []
        dist = 1    # field of view
        ftype = self.map[xy[1]][xy[0]]
        if ftype == FieldType.GRASS.value:
            dist = 2
        elif ftype == FieldType.MOUNTAIN.value:
            dist = 3

        for y in range(0, (dist+1)*2):
            for x in range(0, (dist+1)*2):
                ab = self.translate(x, y, dist)
                a = ab[0]
                b = ab[1]
                if self.map[b][a] == FieldType.UNKNOWN.value:
                    i += 1
        return i

    def msg_rec(self):
        """
        this receives a message from the server and decodes it.
        """
        data = self.clientsocket.recv(1024).decode()
        view = []

        if not data:
            return False

        if data[1] != ' ' and data[1] != 'B':
            print(data)
            return False

        i = int(math.sqrt(len(data)/2))  # diameter viewing distance

        for y in range(0, i):
            row = []
            for x in range(0, i):
                row.append(data[(i*2*y)+x*2])
                if data[(i*2*y)+x*2+1] == 'B':
                    ab = self.translate(x, y, (i-1)/2)
                    a = ab[0]
                    b = ab[1]
                    self.f_scroll = True
                    self.xy_scroll = [a, b]
            view.append(row)

        self.addView(view)
        if self.verbose:
            self.printMap()
        return True

    def moveX(self, i):
        """
        This updates the internal Position.

        :param i: direction of movement
        """
        if i == '0':
            self.xy[1] -= 1
        elif i == '1':
            self.xy[0] += 1
        elif i == '2':
            self.xy[1] += 1
        elif i == '3':
            self.xy[0] -= 1
        self.warpX()
        self.turn += 1

    def printMap(self):
        """
        This prints the internal map with numbers representing line and row numbers.
        """
        ustr = ''
        while len(ustr) < len(str(len(self.map[1]))):
            ustr += ' '
        for i in range(0, len(self.map[1])):
            tstr = "%i:" % i
            ustr += '%5s' % tstr

        print(ustr)     # top row
        for i in range(0, len(self.map)):
            fstr = str(i) + ':'
            while len(fstr) < len(str(len(self.map[1])))+1:
                fstr += ' '
            print(fstr + str(self.map[i]))

    @staticmethod
    def reconstruct_path(came_from, start, goal):
        """
        This has also been taken from: http://www.redblobgames.com/pathfinding/a-star/implementation.html

        :param came_from: a list of tuples representing the chosen path
        :param start: xy pos
        :param goal: py pos of target
        :return:
        """
        current = goal
        path = [current]
        while current != start:
            current = came_from[current]
            path.append(current)
        path.pop()
        path.reverse()
        return path

    def translate(self, x, y, dist):
        """
        This translates coordinates from the server-input to the coordinates on the internal map.

        :param x: x position on the servers massage
        :param y: y position on the servers massage
        :param dist: diameter of the viewing distance
        :return: list containing x, y position, converted to the relative position on the internal map
        """
        a = self.xy[0] + x - dist
        b = self.xy[1] + y - dist
        a = self.warp(a)
        b = self.warp(b)
        return [a, b]

    def warp(self, a):
        return int(a%len(self.map))

    def warpX(self):
        """
        Translates the internal xy position if it gets near te edge.
        """
        self.xy[0] %= len(self.map)
        self.xy[1] %= len(self.map)

    def weight(self, xy, neighbours=0):
        """
        This calculates the weight of a field, don't ask what went through my mind

        :param xy: Field to check
        :param neighbours: determines how many levels of neighbouring fields should
        :return:
        """
        xy[0] = self.warp(xy[0])
        xy[1] = self.warp(xy[1])
        if self.f_Fcast and self.f_scroll:
            uvalue = 150
        else:
            uvalue = 100

        b = {
            FieldType.UNKNOWN.value: uvalue,
            FieldType.GRASS.value: 100,
            FieldType.FOREST.value: 100,
            FieldType.MOUNTAIN.value: 200,
            FieldType.LAKE.value: 9999999,
            FieldType.CASTLE.value: 100
        }[self.map[xy[1]][xy[0]]]

        if not self.f_Fcast and not self.f_scroll:
            b -= self.getNewFields(xy)*5
            b += randint(0, 10)
        if neighbours > 0:
            neighbours -= 1
            c = 0
            for i in self.getNeighbours(xy):
                c += self.weight(i, neighbours)
            b += c/len(self.getNeighbours(xy))
        return b

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--ip-address=', type=str, help='server to connect to', default='localhost', dest='server')
    parser.add_argument(
        '-p', '--port=', type=int, help='port number', default=5050, dest='port')
    parser.add_argument(
        '-s', '--size=', type=int, help='size of the map', default=10, dest='size')
    parser.add_argument(
        '-v', '--verbose', help='if true it displays the steps in the commandline', action="store_true")
    args = parser.parse_args()
    print(args)
    client = ClientController(args.server, args.port, args.size, args.verbose)
