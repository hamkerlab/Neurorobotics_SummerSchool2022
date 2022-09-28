import argparse
import cv2
import sys
import time
import json
import numpy as np
import math

from naoqi import ALProxy
from naoqi import ALBroker
from naoqi import ALModule

def byteify(input):
    if isinstance(input, dict):
        return {byteify(key): byteify(value)
                for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input

class MoveHeadTouch(ALModule):
    '''Execution of Motion Command'''


    def __init__(self, name, params):
        ALModule.__init__(self, name)
        # No need for IP and port here because
        # we have our Python broker connected to NAOqi broker

        self.tts = ALProxy("ALTextToSpeech")
        self.motionProxy = ALProxy("ALMotion")
        self.leds = ALProxy("ALLeds")

        global memory

        # Create proxy to ALMemory
        try:
            memory = ALProxy("ALMemory")
        except Exception as e:
            print("Could not create proxy to ALMemory Error was: {}".format(e))

        self.events_dict = {'FrontTactilTouched': 'Left',
                            'MiddleTactilTouched': 'Center',
                            'RearTactilTouched': 'Right'}

        for k in list(self.events_dict.keys()):
            memory.subscribeToEvent(k, "MoveHeadTouch", "onTouched")

        self.job_handle_voice = self.tts.post.say("Starting the camera")

        self.params = params

        self.body_part = 'Head'
        self.joint_names = ['HeadYaw', 'HeadPitch']

        self.motionProxy.setStiffnesses(self.body_part, self.params['stiffness_val'])

        self.job_handle_motion = self.motionProxy.post.setAngles(self.joint_names,
                                                                 self.params['init_angle'],
                                                                 self.params['fractionMaxSpeed'])

    def onTouched(self, strVarName, value, message):
        """ This will be called each time a touch
        is detected.

        """

        if value > 0:
            if not((self.tts.isRunning(self.job_handle_voice)) | (self.motionProxy.isRunning(self.job_handle_motion))):
                # Unsubscribe to the event when talking, or moving
                # to avoid repetitions
                memory.unsubscribeToEvent(strVarName, "MoveHeadTouch")

                self.job_handle_voice = self.tts.post.say("Looking to my {}".format(self.events_dict[strVarName]))
                self.move_head(self.events_dict[strVarName])
                memory.subscribeToEvent(strVarName, "MoveHeadTouch", "onTouched")

    def move_head(self, command):
        self.motionProxy.setStiffnesses(self.body_part, self.params['stiffness_val'])

        if command == 'Left':
            angles = [45.0, 0.0]
        elif command == 'Center':
            angles = [0.0, 0.0]
        elif command == 'Right':
            angles = [-45.0, 0.0]
        self.job_handle_motion = self.motionProxy.post.setAngles(self.joint_names,
                                                                 [x * math.pi / 180.0 for x in angles],
                                                                 self.params['fractionMaxSpeed'])


def main(ip, port, params_motion, params_cam):
    """ Main entry point
    """
    # We need this broker to be able to construct
    # NAOqi modules and subscribe to other modules
    # The broker must stay alive until the program exists
    myBroker = ALBroker("myBroker",
                        "0.0.0.0",   # listen to anyone
                        0,           # find a free port and use it
                        ip,          # parent broker IP
                        port)        # parent broker port


    global MoveHeadTouch
    MoveHeadTouch = MoveHeadTouch("MoveHeadTouch", params_motion)
    camProxy = ALProxy("ALVideoDevice")

    # subscribe to video device on a specific camera # BGR for opencv
    ''' The webpage to see more details: http://doc.aldebaran.com/2-1/naoqi/vision/alvideodevice-api.html#ALVideoDeviceProxy::subscribeCamera__ssCR.iCR.iCR.iCR.iCR'''
    '''One could call the variable names by loading `vision_definitions` or simply use the index in the correct position:'''
    '''e.g. kQVGA or 1, kBGRColorSpace or 13, it only helps the readability of the code'''
    '''nameID is the handle that later is used to retrieve images or to unsubscribe'''
    nameID = camProxy.subscribeCamera(params_cam['sub_name'],
                                      params_cam['camera_index'],
                                      params_cam['resolution'],
                                      params_cam['color_space'],
                                      params_cam['fps'])
    print("subscribed name handle: {}".format(nameID))
    try:
        frame = None
        # keep looping
        while True:

            key = cv2.waitKey(33) & 0xFF
            if key == ord('q') or key == 27:
                break

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

            # show the frame to our screen
            cv2.imshow("Frame", frame)


    except KeyboardInterrupt:
        print("unsubscribing from {}".format(nameID))
        camProxy.unsubscribe(nameID)
        MoveHeadTouch.motionProxy.setStiffnesses("Head", 0.0)
        print("Interrupted by user, shutting down")
        myBroker.shutdown()
        sys.exit(0)

if __name__ == "__main__":

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

    args = parser.parse_args()

    NAO_name = args.NAO_name
    PORT = args.port


    with open("./config.json", 'r') as stream:
        config = byteify(json.load(stream))

    params_cam = {}
    params_cam['sub_name'] = args.sub_name
    params_cam['camera_index'] = args.camera_index
    params_cam['resolution'] = args.resolution
    params_cam['color_space'] = args.color_space
    params_cam['fps'] = args.fps

    params_motion = {}
    params_motion['stiffness_val'] = 1.0
    params_motion['init_angle'] = [0.0, 0.0]
    params_motion['fractionMaxSpeed'] = 0.2

    main(config['robot_names'][NAO_name], PORT, params_motion, params_cam)
