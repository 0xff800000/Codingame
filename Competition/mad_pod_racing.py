import sys
import math
import numpy as np

# Auto-generated code below aims at helping you parse
# the standard input according to the problem statement.
class PID:
    def __init__(self, kp=1.0, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(None, None)):
        self.kp = kp  # Proportional gain
        self.ki = ki  # Integral gain
        self.kd = kd  # Derivative gain

        self.setpoint = setpoint  # Desired target value

        self._prev_error = 0.0
        self._integral = 0.0

        # Output limits (min, max)
        self.min_output, self.max_output = output_limits

    def update(self, current_value, dt=1.0):
        """
        Calculate PID output with clamping.
        
        :param current_value: The measured system value
        :param dt: Time step (default = 1.0)
        :return: Control output
        """
        error = self.setpoint - current_value

        # Integral term
        self._integral += error * dt

        # Derivative term (avoid division by zero)
        derivative = (error - self._prev_error) / dt if dt > 0 else 0.0

        # PID output
        output = self.kp * error + self.ki * self._integral + self.kd * derivative

        # Apply output limits
        if self.max_output is not None:
            output = min(output, self.max_output)
        if self.min_output is not None:
            output = max(output, self.min_output)

        # Save error for next derivative calculation
        self._prev_error = error

        return output

    def reset(self):
        """Reset the PID controller state."""
        self._prev_error = 0.0
        self._integral = 0.0


class Pod():
    def __init__(self, laps, nb_checkpoints, checkpoints):
        self.laps = laps
        self.nb_checkpoints = nb_checkpoints
        self.checkpoints = checkpoints

        self.pos = np.array([0,0])
        self.boost = False

        self.thrust_pid = PID(kp=100, ki=100, kd=0, setpoint=1.0, output_limits=(0, 100))
    
    def update(self, pos, speed, angle, next_check_point_id):
        self.pos = pos
        self.speed = speed
        self.angle = angle

        target_vec = self.checkpoints[next_check_point_id] - self.pos
        target_dist = np.linalg.norm(target_vec)
        target_angle = np.degrees(np.arctan2(target_vec[1], target_vec[0])) - angle
        target_angle = (target_angle + 180) % 360 - 180
        target_pos = self.checkpoints[next_check_point_id]


        # Correct trajectory by steering against velocity drift
        correction_factor = min(np.linalg.norm(self.speed) / 200.0, 3.0)
        corrected_target = target_pos - self.speed * correction_factor

        # Predictive aiming: aim a bit beyond checkpoint
        steering_dir = corrected_target + (target_pos - self.pos) * 0.2

        # Normalize distance for PID input
        dist_norm = min(target_dist / 6000, 1.0)
        thrust = self.thrust_pid.update(1-dist_norm, 0.075)
        print(thrust, 1-dist_norm, file=sys.stderr, flush=True)


        # Smooth thrust reduction by angle
        angle_factor = max(0, np.cos(np.radians(target_angle)/2))
        #angle_factor = max(0, 1 - abs(target_angle) / 90)
        thrust = int(thrust * angle_factor)

        # BOOST conditions
        if (not self.boost and 
            target_dist > 5000 and 
            abs(target_angle) < 5 and 
            np.linalg.norm(self.speed) > 200):
            thrust = "BOOST"
            self.boost = True

        print(dist_norm, target_dist, angle_factor, target_dist, steering_dir, thrust, file=sys.stderr, flush=True)
        return steering_dir, thrust

# Auto-generated code below aims at helping you parse
# the standard input according to the problem statement.

laps = int(input())
nb_checkpoint = int(input())
checkpoints = []
for i in range(nb_checkpoint):
    checkpoint_x, checkpoint_y = [int(j) for j in input().split()]
    checkpoints.append(np.array([checkpoint_x, checkpoint_y]))

pods = [Pod(laps, nb_checkpoint, checkpoints), Pod(laps, nb_checkpoint, checkpoints)]

# game loop
while True:
    for i in range(2):
        # x: x position of your pod
        # y: y position of your pod
        # vx: x speed of your pod
        # vy: y speed of your pod
        # angle: angle of your pod
        # next_check_point_id: next check point id of your pod
        x, y, vx, vy, angle, next_check_point_id = [int(j) for j in input().split()]
        pos = np.array([x,y])
        speed = np.array([vx,vy])
        steering_dir, thrust = pods[i].update(pos, speed, angle, next_check_point_id)
        print(int(steering_dir[0]), int(steering_dir[1]), thrust)


    for i in range(2):
        # x_2: x position of the opponent's pod
        # y_2: y position of the opponent's pod
        # vx_2: x speed of the opponent's pod
        # vy_2: y speed of the opponent's pod
        # angle_2: angle of the opponent's pod
        # next_check_point_id_2: next check point id of the opponent's pod
        x_2, y_2, vx_2, vy_2, angle_2, next_check_point_id_2 = [int(j) for j in input().split()]

    # Write an action using print
    # To debug: print("Debug messages...", file=sys.stderr, flush=True)

