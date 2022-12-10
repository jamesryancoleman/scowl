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

import pandas as pd
import numpy as np

SRC_ADDR  = sys.argv[1] # includes port, of format '111.111.1.1:32000'
DEST_ADDR = sys.argv[2] # includes port, of format '111.111.1.1:32000'
RTT       = int(sys.argv[3])   # in ms
CAPACITY  = float(sys.argv[4]) # in MW
KIND      = sys.argv[5] # nuclear, petroleum-fired, hydroelectric, natural, gas-fired, land-based wind, offshore wind, utility-scale solar, distributed solar
ID        = None # 32-bit int, use the ip until the id is received

OUTPUT_COEFFICIENTS = None # populated by startMutationEngine(). Rows = months
OUTPUT_PERIOD_LENGTH = 3 # this could/should be user input

output = CAPACITY
state_ts = 0 # lamport ts...
rng = None   # psuedo-rng needs to be global for high entropy 

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
            writer.write('Stopped:      {}\n'.format(stop_time))
        return scowl_pb2.Empty()

def startMutationEngine():
    """call this to set up the mutation state variables"""
    global OUTPUT_COEFFICIENTS
    outputs_matrix = pd.read_csv('sim/2030/generators/config/output_config.csv')
    outputs_matrix.set_index(outputs_matrix.columns[0], inplace=True)
    outputs_matrix.index.names = ['month']
    index = outputs_matrix.index

    _data = {}
    for col in outputs_matrix.columns:
        tuples = []
        for row in outputs_matrix[col]:
            params = str(row)
            params = params[1:-1].split(',')
            if len(params) != 2:
                params = (np.NaN, np.NaN)
            else:
                params = (float(params[0]), float(params[1]))
            tuples.append(params)
        _data[col] = tuples

    outputs_matrix = pd.DataFrame(_data, index = index)

    OUTPUT_COEFFICIENTS = outputs_matrix[KIND]
    return OUTPUT_COEFFICIENTS

def GenOutputCoefficient(mu, sigma, size:int=1,seed=36921):
    """takes parameters from a normal dist.
    returns a list of coefficients.
    """
    global rng
    output = []
    if (np.isnan(mu)):
        output = [0.9] * size
    else:
        if rng is None:
            rng = np.random.default_rng(seed)
        output = rng.normal(mu, sigma, size)
        output = [v if v > 0 else 0.0 for v in output] # remove all negative values
    if size == 1:
        return output[0]
    else:
        return output

def mutateState():
    """when called, it computes to the next state in its sequence"""
    global OUTPUT_COEFFICIENTS, CAPACITY
    global state_ts, output

    if  OUTPUT_COEFFICIENTS is None:
        startMutationEngine()

    # resolves to string
    month = OUTPUT_COEFFICIENTS.index[state_ts % len(OUTPUT_COEFFICIENTS.index)] 
    params = OUTPUT_COEFFICIENTS.loc[month]

    mu = params[0]
    sigma = params[1]
    coef = GenOutputCoefficient(mu, sigma)
    output = CAPACITY * coef

    with open(LOG_PATH.format(ID), 'a') as writer:
            writer.write("--------------- New  State ---------------\n")
            writer.write('Timestamp:    {}\n'.format(state_ts))
            writer.write('Coefficient:  {}\n'.format(coef))
            writer.write('Output:       {}\n'.format(output))

    state_ts += 1

def mutate(stop_event: threading.Event, interval=1):
    while True:
        if stop_event.is_set():
            break
        mutateState()
        time.sleep(interval)

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

def serve(stop_flag: threading.Event):
    """Used to receive TrackerHello message from assigned tracker"""

    generator_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scowl_pb2_grpc.add_GeneratorServicer_to_server(
        GeneratorServicer(stop_flag), generator_server)
    generator_server.add_insecure_port(SRC_ADDR) 
    generator_server.start()
    start_time = datetime.datetime.now().isoformat()
    print("------------- Server Started -------------", )   
    print('Started:      ', start_time)
    print('Callback Addr:', SRC_ADDR)
    with open(LOG_PATH.format(SRC_ADDR), "w") as f:
        f.write("------------- Server Started -------------\n")
        f.write('Started: {}\n'.format(start_time))
    stop_flag.wait()
    generator_server.stop(None)
    # generator_server.wait_for_termination()
    
if __name__ == '__main__':
    # TODO: implement 3 threads of execution:
    #   1. for the run() functions
    #   2. for receiving tracker confirmations 
    #   3. for mutating the generation state and the consumption state,
    #       then updating the tracker.
    
    stop_flag = threading.Event()

    server = threading.Thread(target=serve, args=(stop_flag,))
    server.start()

    intializer = threading.Thread(target=run)
    intializer.start()
    intializer.join()

    mutant = threading.Thread(target=mutate, args=(stop_flag,))
    mutant.start()

    # intializer.join()
    server.join()
    