from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image
from std_msgs.msg import Empty
from ardrone_autonomy.msg import Navdata
import rospy
import cv2
import numpy as np


class VideoBuffer(object):
    def __init__(self,vidfile,start=None,stop=None,historysize=1):
        self.cap = cv2.VideoCapture(vidfile)
        self.name = str(vidfile)
        self.live = not isinstance(vidfile,str)
        self.start = start
        self.stop = stop
        self._buffer = [np.array([])]*historysize
        self._size = historysize

        if not self.live:
            if not self.start:
                self.start = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            else:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.start)
            if not self.stop:
                self.stop = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)

        stat = self.shiftBuffer(self._size)

    def shiftBuffer(self,nshifts=1):
        for i in range(nshifts):
            if not self.live and self.cap.get(cv2.CAP_PROP_POS_FRAMES) == self.stop:
                valid = False
            else:
                valid, img = self.cap.read()

            if valid:
                img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
                time = -1 if self.live else self.cap.get(cv2.CAP_PROP_POS_MSEC)
            else:
                return False

            self._buffer[:-1] = self._buffer[1:]
            self._buffer[-1] = (img,time)
        return True

    def grab(self,frameIdx=1):
        if frameIdx > 0:
            if self.shiftBuffer():
                img, time = self._buffer[-1]
            else:
                img, time = np.array([]), -1
        else:
            img, time = self._buffer[frameIdx-1]
            
        return img, time

    def seek(self,nframes):
        if self.live:
            print "Error: Seek not available with live streams"
        else:
            framenum = self.cap.get(cv2.CAP_PROP_POS_FRAMES)+nframes-self._size
            self.cap.set(cv2.CAP_PROP_POS_FRAMES
                         ,self.stop-self._size if framenum > (self.stop-self._size) else max(self._size,framenum))
            stat = self.shiftBuffer(self._size)

    def close(self):
        self.cap.release()
        del self._buffer


class ROSCamBuffer(object):
    '''
    ROSCamBuffer

    Creates a subcription node to the image publisher and converts the image
    into opencv image type.
    '''
    def __init__(self, topic, historysize=0,buffersize=30):
        self.name=topic
        self.bridge = CvBridge()
        self.image_sub = rospy.Subscriber(topic, Image, self.shiftBuffer)
        self._buffer = [(np.array([]),-1)]*buffersize
        self._size = buffersize
        self._currIdx = 0
        self._histsize = historysize

    def shiftBuffer(self,data):
        try:
            img = self.bridge.imgmsg_to_cv2(data,'bgr8')
            img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        except rospy.ROSException:
            raise
        except KeyboardInterrupt:
            raise

        if (self._currIdx-self._histsize) == -self._size:
            print "ROSCamBuffer: WARNING: Buffer overflow"
        else:
            self._currIdx -= 1

        self._buffer[:-1] = self._buffer[1:]
        self._buffer[-1] = (img,data.msg.header.stamp)

    def grab(self,frameIdx=1):
        if frameIdx > 0:
            try: # spin until the buffer has something in it
                while self._currIdx == 0: None
            except KeyboardInterrupt:
                raise
            img, time = self._buffer[self._currIdx]
            self._currIdx += 1
        elif (self._currIdx-frameIdx) >= -self._size:
            img, time = self._buffer[self._currIdx-frameIdx]
        else:
            img, time = (np.array([]),-1)
            
        return img, time

    def close(self):
        self.image_sub.unregister()
        del self._buffer
