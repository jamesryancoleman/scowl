from concurrent import futures
import datetime
import logging
import grpc


import scowl_pb2
import scowl_pb2_grpc


# this file should start with the general purpose fuctions that the BootstrapServicer class calls.
# 

def LogRequest(request, context):
    print("{} – Request received".format(datetime.datetime.now()))
    print("Request: {} ({})".format(request, type(request)))
    print("Context: {} ({})".format(context, type(context)))


class BootstrapServicer(scowl_pb2_grpc.BootstrapServicer):
    """Provides methods that implement functionality of scowl Bootstrapping server."""
    # // the interfaces exported by the bootstrapping server
    # service Bootstrap {
        # // An RPC for a generator to request credentials from
        # rpc GeneratorJoin(PeerCtx) returns (Id32Bit) {}
        # // An RPC for a consumer to request credentials from
        # rpc ConsumerJoin(PeerCtx) returns (Id128Bit) {}
    # }

    def __init__(self):
        # don't think we need any set up
        pass

    def GeneratorJoin(self, request, context):
        """request: scowl_pb2.PeerCtx # [str]

        returns:
            scowl_pb2.Id32Bit # [int]
        """
        LogRequest(request, context)
        return scowl_pb2.Id32Bit(32000)

    def ConsumerJoin(self, request, context):
        """request: scowl_pb2.PeerCtx # [str]

        returns:
            scowl_pb2.Id32Bit # [int]
        """
        LogRequest(request, context)
        return scowl_pb2.Id128Bit(128000)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scowl_pb2_grpc.add_BootstrapServicer_to_server(
        BootstrapServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    logging.basicConfig()
    serve()