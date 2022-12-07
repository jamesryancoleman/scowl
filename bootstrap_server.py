from concurrent import futures
import datetime
# import logging
import grpc
import mmh3

HASH_SEED = 42 # for use with mmh3

# Scowl specific imports
import scowl_pb2
import scowl_pb2_grpc

# mmh3 has weird deprication warnings. Don't have time to investigate source
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning) 

# log file path
LOG_PATH = 'logs/bootstrap_server.log'

# this file should start with the general purpose fuctions that the 
# BootstrapServicer class calls.

def LogRequest(request, context, response=None, to_log=False):
    if to_log:
        with open(LOG_PATH, 'a') as f:
            f.write('------------ Request Received ------------\n')
            f.write('Date:     {}\n'.format(datetime.datetime.now()))
            f.write('Request:  {}\n'.format(request.addr))
            f.write('Context:  {}\n'.format(context.peer()))
            if response is not None:
                f.write('Response: "{}"\n'.format(response))
            # f.write("------------ Request Handled  ------------\n")
    else:
        print("------------ Request Received ------------")
        print("Date     {}".format(datetime.datetime.now()))
        print("Request  {}".format(request.addr))
        print("Context  {}".format(context.peer()))
        if response is not None:
            print("Response {}".format(response))
        print("------------ Request Handled  ------------")


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
        id_str = id.to_bytes(4, "big", signed=True).decode('unicode_escape')
        LogRequest(request, context, id_str, to_log=True)
        return scowl_pb2.Id32Bit(id=str(id))

    def ConsumerJoin(self, request, context):
        """request: scowl_pb2.PeerCtx # [str]

        returns:
            scowl_pb2.Id32Bit # [int]
        """
        id = mmh3.hash128(request.addr, self.hash_seed)
        id_str = id.to_bytes(16, "big", signed=True).decode('unicode_escape')
        LogRequest(request, context, id_str, to_log=True)
        return scowl_pb2.Id128Bit(id=str(id))

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scowl_pb2_grpc.add_BootstrapServicer_to_server(
        BootstrapServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    start_time = datetime.datetime.now().isoformat()
    print("------------- Server Started -------------", )   
    print('Started:', start_time)
    with open(LOG_PATH, "a") as f:
        f.write("------------- Server Started -------------\n")
        f.write('Started: {}\n'.format(start_time))
    server.wait_for_termination()


if __name__ == '__main__':
    # logging.basicConfig()
    serve()