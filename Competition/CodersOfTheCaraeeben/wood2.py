import sys
import math

def printf(s):
    print(s, file=sys.stderr)

# Euclidian distance between points
def distance(src,dst):
    return math.sqrt((src[0]-dst[0])**2+(src[1]-dst[1])**2)
    #return (abs(src[0] - dst[0]) + abs(src[0] - dst[0]))

def getNearest(me,things):
    distList = []
    for t in things:
        dist = distance((me[0],me[1]),(t[0],t[1]))
        distList.append((dist,t))
    distList.sort()
    return distList[0][1]

# game loop
while True:
    my_ship_count = int(input())  # the number of remaining ships
    entity_count = int(input())  # the number of entities (e.g. ships, mines or cannonballs)
    barrels = []
    myships = []
    enships = []
    cannonballs = []
    mines = []
    for i in range(entity_count):
        # Get the parameters
        entity_id, entity_type, x, y, arg_1, arg_2, arg_3, arg_4 = input().split()
        entity_id = int(entity_id)
        x = int(x)
        y = int(y)
        arg_1 = int(arg_1)
        arg_2 = int(arg_2)
        arg_3 = int(arg_3)
        arg_4 = int(arg_4)

        ent = (x,y,arg_1,arg_2,arg_3,arg_4)

        if entity_type == 'BARREL':
            barrels.append(ent)
        elif entity_type == 'SHIP':
            if arg_4 == 1:
                myships.append(ent)
            else:
                enships.append(ent)
        elif entity_type == 'CANNONBALL':
            cannonballs.append(ent)
        elif entity_type == 'MINE':
            mines.append(ent)

    for ship in myships:
        command = ''
        didsomething = False
        # Deadlock avoidance
        deadlock = False
        if len(enships) != 0:
            if distance(ship,enships[0]) < 3:
                deadlock = True

        # Get barrels
        if len(barrels) != 0:
            target = getNearest(ship,barrels)
            printf('Nearest barrel at {} {}'.format(target[0],target[1]))
            command = "MOVE {} {}".format(target[0],target[1])
            didsomething = True

        # Chase enemys
        if len(barrels) == 0 and len(enships) != 0:
            target = getNearest(ship,enships)
            printf('Nearest enemy at {} {}'.format(target[0],target[1]))
            command = "MOVE {} {}".format(target[0],target[1])
            didsomething = True

        # Shoot enemys
        if (len(barrels) == 0 and len(enships) != 0) or deadlock:
            target = getNearest(ship,enships)
            printf('Nearest enemy at {} {}'.format(target[0],target[1]))
            command = "FIRE {} {}".format(target[0],target[1])
            didsomething = True

        # Destroy mines
        if len(mines) != 0:
            target = getNearest(ship,mines)
            if distance(ship,target) < 2:
                printf('Mine too close')
                command = "FIRE {} {}".format(target[0],target[1])
                didsomething = True

        if didsomething == False:
            command = 'WAIT'

        print(command)