import argparse
import cv2
import sys
import time
import yaml
import numpy as np

from naoqi import ALProxy
from naoqi import ALBroker
from naoqi import ALModule


class ReactToTouch(ALModule):
    '''Streaming Video and Reacting to an Event (ALBroker and ALModule)'''

    def __init__(self, name):
        ALModule.__init__(self, name)
        # No need for IP and port here because
        # we have our Python broker connected to NAOqi broker

        # Create a proxy to ALTextToSpeech for later use
        self.tts = ALProxy("ALTextToSpeech")
        self.motionProxy = ALProxy("ALMotion")
        self.camProxy = ALProxy("ALVideoDevice")

        global memory
        # Create proxy to ALMemory
        try:
            memory = ALProxy("ALMemory")
        except Exception as e:
            print("Could not create proxy to ALMemory Error was: {}".format(e))

        # Subscribe to TouchChanged event:
        memory.subscribeToEvent("MiddleTactilTouched", "ReactToTouch", "onTouched")
        self.job_handle = self.tts.post.say("Starting the camera")

        self.counter = 0

    def onTouched(self, strVarName, value, message):
        """ This will be called each time a touch
        is detected.

        """

        if value > 0:
            if not(self.tts.isRunning(self.job_handle)):
                # Unsubscribe to the event when talking,
                # to avoid repetitions
                memory.unsubscribeToEvent("MiddleTactilTouched", "ReactToTouch")

                self.job_handle = self.tts.post.say("Middle tactile touched.")
                if not(frame is None):
                    cv2.imwrite('./saved_image_{:02d}.jpg'.format(self.counter), frame)
                    self.counter += 1
                memory.subscribeToEvent("MiddleTactilTouched", "ReactToTouch", "onTouched")

def main(ip, port, params_cam):
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


    global ReactToTouch
    ReactToTouch = ReactToTouch("ReactToTouch")
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
    global frame
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

    sub_name = args.sub_name

    camera_index = args.camera_index
    resolution = args.resolution
    color_space = args.color_space
    fps = args.fps

    with open("./config.yaml", 'r') as stream:
        config = yaml.load(stream, Loader=yaml.loader.SafeLoader)

    params = {}
    params['sub_name'] = sub_name
    params['camera_index'] = camera_index
    params['resolution'] = resolution
    params['color_space'] = color_space
    params['fps'] = fps

    main(config['robot_names'][NAO_name], PORT, params)
