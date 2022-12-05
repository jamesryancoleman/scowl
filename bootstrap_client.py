import logging
import grpc

import scowl_pb2
import scowl_pb2_grpc

def getConsumerID(stub):
    """Request a 128-bit id.

    Today, this is a 128-bit hash given an input of an IPv4 address.
        For DDOS resistance, the bootstrap server contenates the received
        IP address with a nonce before hashing.

    In the future, ConsumerID could default to a IPv6 address.
        This would require secondary loadbalancing logic at the trackers.
    """
    return stub.ConsumerJoin(scowl_pb2.PeerCtx(addr='192.168.0.1'))


def getGeneratorID(stub):
    """Request a 32-bit id.

    Today, this is a 32-bit hash given an input of an IPv4 address.
        For the next few decades the number of generators will be relatively
        low (e.g., hundres to low-thousands), so 32-bits is plenty.

        For DDOS resistance, the bootstrap server contenates the received
        IP address with a nonce before hashing.

    In the future, GeneratorID could use an IPv6 address, of 128-bit hash.
        This would require secondary loadbalancing logic at the trackers.
    """
    return stub.GeneratorJoin(scowl_pb2.PeerCtx(addr='192.168.0.2'))

def run():
    # NOTE(gRPC Python Team): .close() is possible on a channel and should be
    # used in circumstances in which the with statement does not fit the needs
    # of the code.
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = scowl_pb2_grpc.BootstrapStub(channel)

        print("-------------- Generator ID --------------")
        gen_id = getGeneratorID(stub)
        print("Received Generator ID: {}".format(gen_id.id))

        print("-------------- Consumer  ID --------------")
        consumer_id = getConsumerID(stub)
        print("Received Consumer ID: {}".format(consumer_id.id))

        print("--------------      FIN     --------------")
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