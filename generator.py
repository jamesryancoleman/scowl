from concurrent import futures
import threading
import datetime
import logging
import grpc
import time
import sys
import os

import scowl_pb2
import scowl_pb2_grpc
import bootstrap_client as client

SRC_ADDR  = sys.argv[1] # includes port, of format '111.111.1.1:32000'
DEST_ADDR = sys.argv[2] # includes port, of format '111.111.1.1:32000'
RTT       = int(sys.argv[3])   # in ms
CAPACITY  = float(sys.argv[4]) # in MW
KIND      = sys.argv[5] # nuclear, petroleum-fired, hydroelectric, natural, gas-fired, land-based wind, offshore wind, utility-scale solar, distributed solar
ID        = None # 32-bit int, use the ip until the id is received

# Received from a TrackerHello
tracker_id = None
tracker_addr = None

# # server pointer used to stop after bootstrapping completed
# generator_server = None

LOG_PATH = 'sim/2030/logs/gen_{}.log'

class GeneratorServicer(scowl_pb2_grpc.GeneratorServicer):
    def __init__(self, stop_event):
        self._stop_event = stop_event

    def ReceiveHello(self, request, context):
        """RPC for receiving TrackerHellos from the designated tracker
        """
        # time.sleep(RTT/1000) # uncomment to add simluated latency
        global ID
        ID = request.gen_id
        tracker_id = request.tracker_id
        tracker_addr = request.tracker_addr

        # rename the log file now that we know the ID
        os.rename(LOG_PATH.format(SRC_ADDR), LOG_PATH.format(ID))
        # global LOG_PATH
        # LOG_PATH = LOG_PATH.format(ID)  
        
        check_metadata=True 
        if check_metadata:
            print("-------------- Hello Received --------------")
            print("Tracker ID:    {}".format(tracker_id))
            print("Tracker Addr:  {}\n".format(tracker_addr))
            print("Tracker says Generator...")
            print(" - Kind =      {} --> {}".format(request.kind,
                KIND == request.kind))
            print(" - Capacity =  {} --> {}".format(request.capacity, 
                CAPACITY == request.capacity))
        return scowl_pb2.Empty()

    def ShutDown(self, request, context):
        """RPC for graceful shutdown of the generators server"""
        self._stop_event.set()
        stop_time = datetime.datetime.now().isoformat()
        print("------------- Server Stopped -------------")  
        print('Stopped:      ', stop_time)
        with open(LOG_PATH.format(ID), 'a') as writer:
            writer.write("------------- Server Stopped -------------\n")
            writer.write('Stopped:      {}'.format(stop_time))
        return scowl_pb2.Empty()           
        
def run():
    gen_id = None
    with grpc.insecure_channel(DEST_ADDR) as channel:
        stub = scowl_pb2_grpc.BootstrapStub(channel)
        gen_id = stub.GeneratorJoin(scowl_pb2.GeneratorCtx(
            addr=SRC_ADDR, kind=KIND, capacity=CAPACITY))
        
    print("---------- Generator Bootstrapped ----------")
    print("Generator ID:  {}".format(gen_id.id))
    print("Type:          {}".format(KIND))
    print("Capacity:      {} MW".format(CAPACITY))
    print("Source Addr:   {}".format(SRC_ADDR))
    print("Dest. Addr:    {}".format(DEST_ADDR))
    print("Dest. rtt:     {} ms".format(RTT))

def serve():
    """Used to receive TrackerHello message from assigned tracker"""
    stop_event = threading.Event()

    generator_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scowl_pb2_grpc.add_GeneratorServicer_to_server(
        GeneratorServicer(stop_event), generator_server)
    generator_server.add_insecure_port(SRC_ADDR) 
    generator_server.start()
    start_time = datetime.datetime.now().isoformat()
    print("------------- Server Started -------------", )   
    print('Started:      ', start_time)
    print('Callback Addr:', SRC_ADDR)
    with open(LOG_PATH.format(SRC_ADDR), "w") as f:
        f.write("------------- Server Started -------------\n")
        f.write('Started: {}\n'.format(start_time))
    stop_event.wait()
    generator_server.stop(None)
    # generator_server.wait_for_termination()
    
if __name__ == '__main__':
    # TODO: implement 3 threads of execution:
    #   1. for the run() functions
    #   2. for receiving tracker confirmations 
    #   3. for mutating the generation state and the consumption state,
    #       then updating the tracker.

    server = threading.Thread(target=serve)
    server.start()

    intializer = threading.Thread(target=run)
    intializer.start()
    intializer.join()

    server.join()
    