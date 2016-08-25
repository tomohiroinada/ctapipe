# Licensed under a 3-clause BSD style license - see LICENSE.rst
# coding: utf8
from time import sleep
from time import time
import zmq
import types
from threading import Thread
import threading
import pickle
from ctapipe.pipeline.zmqpipe.connexions import Connexions


class StagerZmq(threading.Thread, Connexions):

    """`StagerZmq` class represents a Stager pipeline Step.
    It is derived from Thread class.
    It receives new input from its prev stage, thanks to its ZMQ REQ socket,
    and executes its coroutine objet's run method by passing
    input as parameter. Finaly it sends coroutine returned value to its next
    stage, thanks to its ZMQ REQ socket,
    The Thread is launched by calling run method, after init() method
    has been called and has returned True.
    The thread is stoped by executing finish method.
    """

    def __init__(
            self, coroutine, sock_job_for_me_port,
            name=None, connexions=dict(),main_connexion_name=None, gui_address=None):
        """
        Parameters
        ----------
        coroutine : Class instance that contains init, run and finish methods
        sock_job_for_me_port: str
            Port number for input socket url
        sock_job_for_you_port: str
            Port number for output socket url
        """
        # Call mother class (threading.Thread) __init__ method
        Thread.__init__(self)
        self.name = name
        Connexions.__init__(self,main_connexion_name,connexions)

        # Set coroutine
        self.coroutine = coroutine
        # set sockets url
        self.sock_job_for_me_url = 'inproc://' + sock_job_for_me_port

        self.running = False
        self.nb_job_done = 0
        self.gui_address = gui_address
        self.done = False
        self.waiting_since = 0

        # Prepare our context and sockets
        #context = zmq.Context.instance()
        #self.main_out_socket = context.socket(zmq.REQ)


    def init(self):
        """
        Initialise coroutine sockets and poller
        Returns
        -------
        True if coroutine init method returns True, otherwise False
        """
        if self.name is None:
            self.name = "STAGER"
        if self.coroutine is None:
            return False
        if self.coroutine.init() == False:
            return False
        #self.coroutine.send_msg = self.send_msg

        # Connect to GUI
        context = zmq.Context.instance()
        self.socket_pub = context.socket(zmq.PUB)
        if self.gui_address is not None:
            self.socket_pub.connect("tcp://" + self.gui_address)

        self.sock_for_me = context.socket(zmq.REQ)
        self.sock_for_me.connect(self.sock_job_for_me_url)

        # Use a ZMQ Pool to get multichannel message
        self.poll = zmq.Poller()
        # Register sockets
        self.poll.register(self.sock_for_me, zmq.POLLIN)
        # Send READY to next_router to inform about my capacity to compute new
        # job
        self.sock_for_me.send_pyobj("READY")
        # Stop flag
        self.stop = False
        return True

    def run(self):
        """
        Method representing the thread’s activity.
        It polls its socket and when received new input from it,
        it executes coroutine run method by passing new input.
        Then it sends coroutine return value to its next stage,
        thanks to its ZMQ REQ socket.
        The poll method's timeout is 100 ms in case of self.stop flag
        has been set to False by finish method.
        """
        while not self.stop:

            sockets = dict(self.poll.poll(100))  # Poll or time out (100ms)
            if (self.sock_for_me in sockets and
                    sockets[self.sock_for_me] == zmq.POLLIN):
                #  Get the input from prev_stage
                self.waiting_since = 0
                self.running = True
                self.update_gui()
                request = self.sock_for_me.recv_multipart()
                receiv_input = pickle.loads(request[0])
                # do the job
                results = self.coroutine.run(receiv_input)
                destination = None
                if isinstance(results, types.GeneratorType):
                    for val in results:
                        if isinstance(val,tuple) and len(val)>1:
                            destination = val[1]
                            msg = val[0]
                        else:
                            msg = val
                        self.send_msg(msg,destination)
                else:
                    if isinstance(results,tuple) and len(results)>1:
                        destination = results[1]
                        msg = results[0]
                    else:
                        msg = results
                    self.send_msg(msg,destination)
                # send acknoledgement to prev router/queue to inform it that I
                # am available
                self.sock_for_me.send_multipart(request)
                self.nb_job_done += 1
                self.running = False
                self.update_gui()
            else:
                self.waiting_since+=100 # 100 ms
        self.sock_for_me.close()
        self.socket_pub.close()
        self.done = True

    def finish(self):
        """
        Executes coroutine method and set stop flag to True to stop
        Thread activity
        """
        self.coroutine.finish()
        self.stop = True
        if self.done:
            return True
        else:
            return False

    def update_gui(self):
        msg = [self.name, self.running, None]
        self.socket_pub.send_multipart(
            [b'GUI_STAGER_CHANGE', pickle.dumps(msg)])
