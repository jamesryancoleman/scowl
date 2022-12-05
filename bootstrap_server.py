from concurrent import futures
import datetime
import logging
import grpc
import mmh3

HASH_SEED = 42 # for use with mmh3

# Scowl specific imports
import scowl_pb2
import scowl_pb2_grpc

# mmh3 has weird deprication warnings. Don't have time to investigate source
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning) 

# this file should start with the general purpose fuctions that the 
# BootstrapServicer class calls.

def LogRequest(request, context, response=None):
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
        LogRequest(request, context, id_str)
        return scowl_pb2.Id32Bit(id=str(id))

    def ConsumerJoin(self, request, context):
        """request: scowl_pb2.PeerCtx # [str]

        returns:
            scowl_pb2.Id32Bit # [int]
        """
        id = mmh3.hash128(request.addr, self.hash_seed)
        id_str = id.to_bytes(16, "big", signed=True).decode('unicode_escape')
        LogRequest(request, context, id_str)
        return scowl_pb2.Id128Bit(id=str(id))

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scowl_pb2_grpc.add_BootstrapServicer_to_server(
        BootstrapServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("------------- Server Started -------------")
    server.wait_for_termination()


if __name__ == '__main__':
    logging.basicConfig()
    serve()