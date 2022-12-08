"""
A tracker must:
    1. receive generator registration data from the bootstrapping server
    2. hold that state
    3. receive updates from generators on new consumption
    4. pass consumption from generator to generator.
        4a. unit size of consumption passed: 1 home / 0.00131 MW
"""
from concurrent import futures
import datetime
import grpc

import scowl_pb2
import scowl_pb2_grpc

# log file path
LOG_PATH = 'logs/tracker.log'

RES_CONSUMPTION = 0.00131 # MW

def LogRequest(request, context, response=None, to_log=False):
    if to_log:
        with open(LOG_PATH, 'a') as f:
            f.write('------------ Request Received ------------\n')
            f.write('Date:     {}\n'.format(datetime.datetime.now()))
            f.write('ID:       {}\n'.format(request.id))
            f.write('Src Addr: {}\n'.format(request.addr))
            f.write('Type:     "{}"\n'.format(request.kind))
            f.write('Capacity: {}\n'.format(request.capacity))
    else:
        print("------------ Request Received ------------")
        print("Date     {}".format(datetime.datetime.now()))
        # print("Request  {}".format(request.addr))
        # print("Context  {}".format(context.peer()))
        # if response is not None:
        #     print("Response {}".format(response))

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
        return scowl_pb2.Empty()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scowl_pb2_grpc.add_TrackerServicer_to_server(
        TrackerServicer(), server)
    server.add_insecure_port('[::]:50052') # one higher than Bootstrap server
    server.start()
    start_time = datetime.datetime.now().isoformat()
    print("------------- Tracker Started -------------", )   
    print('Started:', start_time)
    with open(LOG_PATH, "a") as f:
        f.write("------------- Tracker Started -------------\n")
        f.write('Started: {}\n'.format(start_time))
    server.wait_for_termination()


if __name__ == '__main__':
    serve()