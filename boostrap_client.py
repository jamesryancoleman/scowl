import logging
import grpc

import scowl_pb2
import scowl_pb2_grpc

def getConsumerID():
    """Request a 128-bit id.

    Today, this is a 128-bit hash given an input of an IPv4 address.
        For DDOS resistance, the bootstrap server contenates the received
        with a nonce before hashing.

    In the future, ConsumerID could default to a IPv6 address.
        This would require secondary loadbalancing logic at the trackers.
    """
    pass

def getGeneratorID():
    """Request a 32-bit id.

    Today, this is a 32-bit hash given an input of an IPv4 address.
        For DDOS resistance, the bootstrap server contenates the received
        with a nonce before hashing.

    In the future, GeneratorID could default to an IPv6 address.
        This would require secondary loadbalancing logic at the trackers.
    """
    pass

def run():
    # NOTE(gRPC Python Team): .close() is possible on a channel and should be
    # used in circumstances in which the with statement does not fit the needs
    # of the code.
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = scowl_pb2_grpc.RouteGuideStub(channel)

        # print("-------------- GetFeature --------------")
        # guide_get_feature(stub)
        # print("-------------- ListFeatures --------------")
        # guide_list_features(stub)
        # print("-------------- RecordRoute --------------")
        # guide_record_route(stub)
        # print("-------------- RouteChat --------------")
        # guide_route_chat(stub)


if __name__ == '__main__':
    logging.basicConfig()
    run()