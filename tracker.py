"""
A tracker must:
    1. receive generator registration data from the bootstrapping server
    2. hold that state
    3. receive updates from generators on new consumption
    4. pass consumption from generator to generator.
        4a. unit size of consumption passed: 1 home / 0.00131 MW
"""
from concurrent import futures
import numpy as np
import datetime
import typing
import grpc

import scowl_pb2
import scowl_pb2_grpc

import sys

# Generator hash size (bits)
HASH_SIZE = 32

# port to host the tracker on
LISTEN_PORT = int(sys.argv[1]) # [0] is the program name
HOST_ID = int(sys.argv[2])
TRACKER_ID = LISTEN_PORT - 32000
NUM_BUCKETS = int(sys.argv[3]) # int

# log file path
LOG_PATH = 'sim/2030/logs/host_{}_tracker_{}.log'.format(HOST_ID, TRACKER_ID)

RES_CONSUMPTION = 0.00131 # MW

def ComputeBucketRange(num_buckets: int = NUM_BUCKETS, bucket_id: int = TRACKER_ID, hash_size: int = 32):
    break_points = np.linspace((2**(hash_size-1) * -1), (2**(hash_size-1)), num_buckets + 1, dtype=int)
    lower = break_points[bucket_id]
    upper = break_points[bucket_id+1]
    return lower, upper

def LogRequest(request, context, response=None, to_log=False, to_stdout=True):
    if to_log:
        with open(LOG_PATH, 'a') as f:
            f.write('------------ Request Received ------------\n')
            f.write('Date:     {}\n'.format(datetime.datetime.now()))
            f.write('ID:       {}\n'.format(request.id))
            f.write('Src Addr: {}\n'.format(request.addr))
            f.write('Type:     "{}"\n'.format(request.kind))
            f.write('Capacity: {}\n'.format(request.capacity))
    if to_stdout:
        print("------------ New Generator ------------")
        print("Date     {}".format(datetime.datetime.now()))
        print("ID       {}".format(request.id))
        print('Type:    "{}"\n'.format(request.kind))
        # print("Request  {}".format(request.addr))
        # print("Context  {}".format(context.peer()))
        # if response is not None:
        #     print("Response {}".format(response))

def SendGeneratorHello(request):
    """Reach out to the Generator"""
    with grpc.insecure_channel(request.addr) as channel:
        stub = scowl_pb2_grpc.GeneratorStub(channel)
        stub.ReceiveHello(scowl_pb2.TrackerHello(
            tracker_addr='localhost' + ':' + str(LISTEN_PORT),
            tracker_id=TRACKER_ID,
            gen_id=request.id,
            kind=request.kind,
            capacity=request.capacity)) # returns None

class TrackerServicer(scowl_pb2_grpc.TrackerServicer):
    """Provides methods that implement functionality of the scowl Tracker server"""
    def __init__(self):
        self.Generators = {}

    def RegisterGenerator(self, request, context):
        """request: scowl_pb2.GeneratorMetadata 

        returns:
            scowl_pb2.Empty
        """
        self.Generators[request.id] = request
        LogRequest(request, context, to_log=True)
        SendGeneratorHello(request)
        return scowl_pb2.Empty()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scowl_pb2_grpc.add_TrackerServicer_to_server(
        TrackerServicer(), server)
    server.add_insecure_port('[::]:' + str(LISTEN_PORT)) # one higher than Bootstrap server
    server.start()
    start_time = datetime.datetime.now().isoformat()
    print("------------- Tracker Started -------------", )   
    print('Started:', start_time)
    with open(LOG_PATH, "w") as f:
        f.write("------------- Tracker Started -------------\n")
        f.write('Started: {}\n'.format(start_time))
    server.wait_for_termination()


if __name__ == '__main__':
    # TODO: add threading for:
    #   1. Receiving generator bootstrap calls and issuing ACKs to genereators
    print("Tracker {} is responsible for:".format(TRACKER_ID))
    lower, upper = ComputeBucketRange(NUM_BUCKETS, TRACKER_ID, HASH_SIZE) 
    print("IDs [{} , {})".format(lower, upper))
    serve()