import argparse
import cv2
import numpy as np
from naoqi import ALProxy
import time
import os
import yaml

global motionProxy, camProxy

def GetImage(frame, nameID):
    # obtain image
    naoImage = camProxy.getImageRemote(nameID)

    '''The 6th index contains the array of the image.'''
    '''However, this array should be reshaped to the correct dimension (e.g. width and height)'''
    # extract fields
    width = naoImage[0]
    height = naoImage[1]
    nchannels = naoImage[2]
    imgbuffer = naoImage[6]

    # build opencv image (allocate on first pass)
    if frame is None:
        print('Obtained image of size {} x {}, with {} channels'.format(width, height, nchannels))
        frame = np.asarray(bytearray(imgbuffer), dtype=np.uint8)
        frame = frame.reshape((height, width, nchannels))
    else:
        frame.data = bytearray(imgbuffer)

    return frame


def DetectBall(frame, colorLower, colorUpper):
    # Smoothing Images
    # http://docs.opencv.org/master/d4/d13/tutorial_py_filtering.html#gsc.tab=0
    blurred = cv2.GaussianBlur(frame, (11, 11), 0)
    # Converts an image from one color space to another
    # http://docs.opencv.org/master/df/d9d/tutorial_py_colorspaces.html#gsc.tab=0
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # construct a mask for the color, then perform
    #  a series of dilations and erosions to remove any small
    # blobs left in the mask
    mask = cv2.inRange(hsv, colorLower, colorUpper)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)

    cv2.imshow("mask", mask)

    # find contours in the mask and initialize the current
    # (x, y) center of the ball
    cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL,
                            cv2.CHAIN_APPROX_SIMPLE)[-2]
    center = None

    # only proceed if at least one contour was found
    if len(cnts) > 0:
        # find the largest contour in the mask, then use
        # it to compute the minimum enclosing circle and
        # centroid
        c = max(cnts, key=cv2.contourArea)
        ((x, y), radius) = cv2.minEnclosingCircle(c)
        M = cv2.moments(c)
        center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

        # only proceed if the radius meets a minimum size
        # if radius > 10: # TODO: why is this removed?
        # draw the circle and centroid on the frame,
        # then update the list of tracked points
        cv2.circle(frame, (int(x), int(y)), int(radius),
                   (0, 255, 255), 2)
        cv2.circle(frame, center, 5, (0, 0, 255), -1)

    return frame, center


if __name__ == "__main__":
    '''Tracking a colored Ball'''

    parser = argparse.ArgumentParser(description="Getting to know NAO")
    parser.add_argument('--NAO_name', type=str, default='sleepy',
                        help='The name of the NAO robot, it should be one of the seven dwarves from Snow White.')
    parser.add_argument('--port', type=int, default=9559,
                        help='Port, through which it will connect to NAO.')
    parser.add_argument('--sub_name', type=str, default='NAO_cam',
                        help='Just a name assigned to the subscribed module. '
                             'If one forgot to unsubscribe at the end of the routine, one should definitely change this name.')
    parser.add_argument('--camera_index', type=int, default=0,
                        help='0 is the top camera and 1 is the bottom camera.')
    parser.add_argument('--resolution', type=int, default=2,
                        help='0 -> 160x120, 1 -> 320x240, 2 -> 640x480, ...')
    parser.add_argument('--color_space', type=int, default=13,
                        help='color space, for instance kBGRColorSpace is 13 and kYuvColorSpace is 0.')
    parser.add_argument('--fps', type=int, default=30,
                        help='frame rate could be between 1 and 30.')

    parser.add_argument('--ball_color', type=str, default='red',
                        help='The color of the ball to be tracked, e.g. red, blue, etc.')

    args = parser.parse_args()

    NAO_name = args.NAO_name
    PORT = args.port

    with open("./config.yaml", 'r') as stream:
        config = yaml.load(stream, Loader=yaml.loader.SafeLoader)

    tts = ALProxy("ALTextToSpeech", config['robot_names'][NAO_name], PORT)
    motionProxy = ALProxy("ALMotion", config['robot_names'][NAO_name], PORT)
    memProxy = ALProxy("ALMemory", config['robot_names'][NAO_name], PORT)

    # Create a proxy for ALVideoDevice
    camProxy = ALProxy("ALVideoDevice", config['robot_names'][NAO_name], PORT)

    # subscribe to video device on a specific camera # BGR for opencv
    ''' The webpage to see more details: http://doc.aldebaran.com/2-1/naoqi/vision/alvideodevice-api.html#ALVideoDeviceProxy::subscribeCamera__ssCR.iCR.iCR.iCR.iCR'''
    '''One could call the variable names by loading `vision_definitions` or simply use the index in the correct position:'''
    '''e.g. kQVGA or 1, kBGRColorSpace or 13, it only helps the readability of the code'''
    '''nameID is the handle that later is used to retrieve images or to unsubscribe'''
    nameID = camProxy.subscribeCamera(args.sub_name,
                                      args.camera_index,
                                      args.resolution,
                                      args.color_space,
                                      args.fps)
    print("subscribed name handle: {}".format(nameID))

    # http://colorizer.org/
    # define the lower and upper boundaries of the "yellow"
    # ball in the HSV color space, then initialize the
    # yellow: 53,76,100

    color_bounds = {'yellow': [(10, 150, 150), (50, 255, 255)],
                    'blue': [(70, 150, 50), (150, 255, 255)],
                    'red': [(160, 150, 50), (180, 255, 255)]}

    # Set Viewing direction of NAO in the beginning to [0,0] (infront)

    joint_names = ["HeadYaw", "HeadPitch"]
    init_angle = [0.0, 0.0]
    fractionMaxSpeed = 0.2
    stiffness_val = 1.0
    body_name = "Head"
    motionProxy.setStiffnesses(body_name, stiffness_val)

    motionProxy.setAngles(joint_names, init_angle, fractionMaxSpeed)

    time.sleep(2.0)

    try:
        frame = None
        # keep looping
        while True:
            key = cv2.waitKey(33) & 0xFF
            if key == ord('q') or key == 27:
                break

            frame = GetImage(frame, nameID)
            frame, center = DetectBall(frame, color_bounds[args.ball_color][0], color_bounds[args.ball_color][1])

            # show the frame to our screen
            cv2.imshow("frame", frame)

            # TODO: implement the routine for the head to follow the ball based on the center value.

    finally:  # if anything goes wrong we'll make sure to unsubscribe
        print("unsubscribing from {}".format(nameID))
        camProxy.unsubscribe(nameID)
        motionProxy.setStiffnesses(body_name, 0.0)
