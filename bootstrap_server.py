from concurrent import futures
import numpy as np
import datetime
# import logging
import grpc
import mmh3
import sys

HASH_SEED = 42 # for use with mmh3

# Scowl specific imports
import scowl_pb2
import scowl_pb2_grpc

# mmh3 has weird deprication warnings. Don't have time to investigate source
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

HASH_SIZE = 32 # bits

# log file path
LOG_PATH = 'sim/2030/logs/bootstrap_server.log'

# Tracker IP address and port
NUM_TRACKERS = int(sys.argv[1]) # used to compute the port and host IP of tracker
TRACKER_HOST = 'localhost'
TRACKER_PORT = 32000
TRACKER_ADDR = TRACKER_HOST + ':' + str(TRACKER_PORT)
TRACKER_HASH_RANGES = np.linspace((2**(HASH_SIZE-1) * -1), (2**(HASH_SIZE-1)), NUM_TRACKERS + 1, dtype=int)

# Path to Tracker Host IPs
TRACKER_CONFIG = 'sim/2030/trackers/config/tracker_addrs.txt'

# this will store the tracker address book
tracker_lookup = {}

def LoadTrackers(path: str = TRACKER_CONFIG):
    """takes a path and returns the ip addresses found there"""
    file = ""
    with open(path, 'r') as reader:
        file = reader.read()
    return file.split('\n')

# tracker IP addresses
TRACKER_IPS = LoadTrackers(TRACKER_CONFIG)

def LogRequest(request, context, response=None, to_log=False):
    if to_log:
        with open(LOG_PATH, 'a') as f:
            f.write('------------ Request Received ------------\n')
            f.write('Date:     {}\n'.format(datetime.datetime.now()))
            f.write('From:     {}\n'.format(request.addr))
            # f.write('Context:  {}\n'.format(context.peer()))
            f.write('Type:     "{}"\n'.format(request.kind))
            f.write('Capacity: {}\n'.format(request.capacity))
            if response is not None:
                f.write('Response: {}\n'.format(response))
            # f.write("------------ Request Handled  ------------\n")
    else:
        print("------------ Request Received ------------")
        print("Date     {}".format(datetime.datetime.now()))
        print("Gen addr {}".format(request.addr))
        print("Type     {}".format(request.kind))
        print("Capacity {}".format(request.capacity))
        print("Context  {}".format(context.peer()))
        if response is not None:
            print("Response {}".format(response))
        print("------------ Request Handled  ------------")

def GetTrackerLookup(num_trackers: int = NUM_TRACKERS, starting_port: int = TRACKER_PORT, hosts = 'localhost'):
    lookup = {}
    for i in range(num_trackers):
        lookup[i] = {'host_id': 0, 'addr': 'localhost', 'port': str(starting_port + i)}
    if hosts != 'localhost':
        for i in range(num_trackers):
            lookup[i]['host_id'] = i % len(hosts)
            lookup[i]['addr'] = hosts[i % len(hosts)]
    return lookup

def AssignBucket(hash_result: int, num_buckets=NUM_TRACKERS, break_points = None, hash_size=HASH_SIZE):
    break_points = break_points
    if break_points is None:
        break_points = np.linspace((2**(hash_size-1) * -1), (2**(hash_size-1)), num_buckets + 1, dtype=int)
    bucket = None
    for i in range(num_buckets):
        if (hash_result >= break_points[i]) and (hash_result < break_points[i+1]):
            bucket = i
            break
    return bucket

def ShareNewGenerator(tracker_addr, gen_addr, id, kind, capacity):
    """Share new Generator w/ Tracker"""
    with grpc.insecure_channel(tracker_addr) as channel:
        stub = scowl_pb2_grpc.TrackerStub(channel)
        stub.RegisterGenerator(scowl_pb2.GeneratorMetadata(
            addr=gen_addr,
            id=id,
            kind=kind,
            capacity=capacity)) # returns None
    print("--- Triaged Generator ---")
    print("ID: {}".format(id))

def GetOwnIP():
    import socket   
    hostname=socket.gethostname()   
    IPAddr=socket.gethostbyname(hostname)
    return IPAddr


class BootstrapServicer(scowl_pb2_grpc.BootstrapServicer):
    """Provides methods that implement functionality of scowl Bootstrapping server."""
    def __init__(self):
        self.hash_seed = HASH_SEED

    def GeneratorJoin(self, request, context):
        """request: scowl_pb2.PeerCtx # [str]

        returns:
            scowl_pb2.Id32Bit # [int]
        """
        id = mmh3.hash(request.addr, self.hash_seed)
        # id_str = id.to_bytes(4, "big", signed=True).decode('unicode_escape')
        LogRequest(request, context, id, to_log=True)
        # TODO: replace addr with a value from the tracker_lookup,
        #       and 
        tracker_id = AssignBucket(id, break_points=TRACKER_HASH_RANGES)
        tracker_addr = tracker_lookup[tracker_id]['addr'] + ":" + tracker_lookup[tracker_id]['port']
        ShareNewGenerator(tracker_addr, request.addr, str(id), request.kind, request.capacity)
        print("Assigned Gen_<{}> to Tracker_{} @ {}".format(id, tracker_id, tracker_addr))
        return scowl_pb2.Id32Bit(id=str(id))

    def ConsumerJoin(self, request, context):
        """request: scowl_pb2.PeerCtx # [str]

        returns:
            scowl_pb2.Id32Bit # [int]
        """
        id = mmh3.hash128(request.addr, self.hash_seed)
        # id_str = id.to_bytes(16, "big", signed=True).decode('unicode_escape')
        LogRequest(request, context, id, to_log=True)
        return scowl_pb2.Id128Bit(id=str(id))

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scowl_pb2_grpc.add_BootstrapServicer_to_server(
        BootstrapServicer(), server)
    addr = GetOwnIP() + ':' + '50051'
    server.add_insecure_port('[::]:50051') # 
    server.start()
    start_time = datetime.datetime.now().isoformat()
    print("------------- Server Started -------------", )   
    print('Started: ', start_time)
    print('Addr:    ', addr)
    with open(LOG_PATH, "w") as f:
        f.write("------------- Server Started -------------\n")
        f.write('Started: {}\n'.format(start_time))
    server.wait_for_termination()

if __name__ == '__main__':
    # logging.basicConfig()
    # ips = LoadTrackers()
    # tracker_lookup = GetTrackerLookup(hosts=ips)
    tracker_lookup = GetTrackerLookup()
    print("------------- Known Trackers -------------")
    for tracker_id in tracker_lookup:
        print(tracker_id, tracker_lookup[tracker_id])
    serve()