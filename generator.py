import logging
import grpc
import sys

import scowl_pb2
import scowl_pb2_grpc
import bootstrap_client as client

SRC_ADDR  = sys.argv[1] # includes port, of format '111.111.1.1:32000'
DEST_ADDR = sys.argv[2] # includes port, of format '111.111.1.1:32000'
RTT       = int(sys.argv[3]) # in ms
CAPACITY  = float(sys.argv[4]) # in MW
KIND      = sys.argv[5] # nuclear, petroleum-fired, hydroelectric, natural, gas-fired, land-based wind, offshore wind, utility-scale solar, distributed solar

def run():
    gen_id = None
    with grpc.insecure_channel(DEST_ADDR) as channel:
        stub = scowl_pb2_grpc.BootstrapStub(channel)
        gen_id = stub.GeneratorJoin(scowl_pb2.GeneratorCtx(
            addr=SRC_ADDR, kind=KIND, capacity=CAPACITY))
        
    print("-------------- New Generator --------------")
    print("Generator ID: {}".format(gen_id.id))
    print("Type:         {}".format(KIND))
    print("Capacity:     {} MW".format(CAPACITY))
    print("Source Addr:  {}".format(SRC_ADDR))
    print("Dest. Addr:   {}".format(DEST_ADDR))
    print("Dest. rtt:    {}".format(RTT))
    
if __name__ == '__main__':
    run()