import argparse
import cv2
import json
import numpy as np
from naoqi import ALProxy

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

if __name__ == "__main__":
    '''Streaming Video and Middle Tactile Touch Detection'''

    parser = argparse.ArgumentParser(description="Getting to know NAO")
    parser.add_argument('--NAO_name', type=str, default='sleepy',
                        help='The name of the NAO robot, it should be one of the seven dwarves from Snow White.')
    parser.add_argument('--port', type=int, default=9559,
                        help='Port, through which it will connect to NAO.')
    parser.add_argument('--sub_name', type=str, default='nao_cam',
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

    tts = ALProxy("ALTextToSpeech", config['robot_names'][NAO_name], PORT)
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
    p_handle = tts.post.say("Starting the camera")
    counter = 0
    try:
        frame = None
        # keep looping
        while True:
            key = cv2.waitKey(33) & 0xFF
            if key == ord('q') or key == 27:
                break

            MiddleTactileON = memProxy.getData('Device/SubDeviceList/Head/Touch/Middle/Sensor/Value')

            if (MiddleTactileON):

                if not(tts.isRunning(p_handle)):
                    p_handle = tts.post.say("Middle tactile touched.")
                    if not(frame is None):
                        cv2.imwrite('./saved_image_{:02d}.jpg'.format(counter), frame)
                        counter += 1

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

    finally:  # if anything goes wrong we'll make sure to unsubscribe
        print("unsubscribing from {}".format(nameID))
        camProxy.unsubscribe(nameID)

