import sys
import math

def distance(src,dst):
    return math.sqrt((src(1)-src(2))**2+(dst(1)-dst(2))**2)

# game loop
while True:
    my_ship_count = int(input())  # the number of remaining ships
    entity_count = int(input())  # the number of entities (e.g. ships, mines or cannonballs)
    barrels = []
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

        if entity_type == 'BARREL':
            barrels.append((x,y,arg_1,arg_2,arg_3,arg_4))

    for i in range(my_ship_count):

        # Write an action using print
        # To debug: print("Debug messages...", file=sys.stderr)

        # Any valid action, such as "WAIT" or "MOVE x y"
        print("MOVE {} {}".format(barrels[0][0],barrels[0][1]))
