"""
A tracker must:
    1. receive generator registration data from the bootstrapping server
    2. hold that state
    3. receive updates from generators on new consumption
    4. pass consumption from generator to generator.
        4a. unit size of consumption passed: 1 home / 0.00131 MW
"""
from concurrent import futures
from tabulate import tabulate
import pandas as pd
import numpy as np
import datetime
import typing
import grpc
import time

import scowl_pb2
import scowl_pb2_grpc

import sys
# Generator hash size (bits)
HASH_SIZE = 32
START_PORT = 32000

# port to host the tracker on
LISTEN_PORT = int(sys.argv[1]) # [0] is the program name
HOST_ID = int(sys.argv[2])
TRACKER_ID = LISTEN_PORT - START_PORT
NUM_BUCKETS = int(sys.argv[3]) # int

# log file path
LOG_PATH = 'sim/2030/logs/host_{}_tracker_{}.log'.format(HOST_ID, TRACKER_ID)
DATA_PATH = 'sim/2030/logs/his/host_{}_tracker_{}.csv'.format(HOST_ID, TRACKER_ID)

# Electricity Stuff
RES_CONSUMPTION = 0.00131 # MW
SAFETY_THRESHOLD = 0.1    # 10% of generator output

# a data frame with columns per STATE_COLUMNS and generators as rows
STATE_COLUMNS = ['ts', 'host','tracker','output', 'demand', 'net_cap', 'percent_use','time']

state = pd.DataFrame(columns=STATE_COLUMNS)
state.index.name = 'id'
state.to_csv(DATA_PATH) # start a new log

def GetOwnIP():
    import socket   
    hostname=socket.gethostname()   
    IPAddr=socket.gethostbyname(hostname)
    return IPAddr

def ComputeBucketRange(num_buckets: int = NUM_BUCKETS, bucket_id: int = TRACKER_ID, hash_size: int = 32):
    break_points = np.linspace((2**(hash_size-1) * -1), (2**(hash_size-1)), num_buckets + 1, dtype=int)
    lower = break_points[bucket_id]
    upper = break_points[bucket_id+1]
    return lower, upper

def LogRequest(request, context, response=None, to_log=False, to_stdout=True):
    if to_log:
        with open(LOG_PATH, 'a') as f:
            f.write('------------ Request Received ------------\n')
            f.write('Date:     {}\n'.format(datetime.datetime.now()))
            f.write('ID:       {}\n'.format(request.id))
            f.write('Src Addr: {}\n'.format(request.addr))
            f.write('Type:     "{}"\n'.format(request.kind))
            f.write('Capacity: {}\n'.format(request.capacity))
    if to_stdout:
        print("------------ New Generator ------------")
        print("Date     {}".format(datetime.datetime.now()))
        print("ID       {}".format(request.id))
        print('Type:    "{}"\n'.format(request.kind))
        # print("Request  {}".format(request.addr))
        # print("Context  {}".format(context.peer()))
        # if response is not None:
        #     print("Response {}".format(response))

def SendGeneratorHello(request):
    """Reach out to the Generator"""
    time.sleep(0.2)
    with grpc.insecure_channel(request.addr) as channel:
        stub = scowl_pb2_grpc.GeneratorStub(channel)
        stub.ReceiveHello(scowl_pb2.TrackerHello(
            tracker_addr='localhost' + ':' + str(LISTEN_PORT),
            tracker_id=TRACKER_ID,
            gen_id=request.id,
            kind=request.kind,
            capacity=request.capacity)) # returns None

def LoadBalance(id):
    global state

    df = state.copy() # make a copy of the state
    previous_load = state.loc[id].demand

    # add 'safety' metrics for safe demand and safe net capacity.
    # the safety threshold is 10% (0.1) for all generators
    df['s_demand'] = np.round((df.output * (1 - SAFETY_THRESHOLD)), 2)
    df['s_net_cap'] =  df['s_demand'] - df['demand']

    # create views of the state for generators in safe and unsafe state
    surplus = df[df['percent_use'] > SAFETY_THRESHOLD].copy()
    deficit = df[df['percent_use'] < SAFETY_THRESHOLD].copy()

    # if len(deficit) < 1:
    #     print('{}.{}: {} left in the deficit group'.format(id, int(_ts) ,len(deficit)))

    net_system_cap = surplus.net_cap.sum() - deficit.net_cap.sum()
    total_safe_capacity = (surplus.output * (1 - SAFETY_THRESHOLD) - surplus.demand).sum()

    safe_load   = (df.output * (1 - SAFETY_THRESHOLD)).sum()
    unsafe_load = (deficit.output * (1 - SAFETY_THRESHOLD) - deficit.demand).sum()

    # when the error occurs, there is no unsafe load
    if unsafe_load < 0:
        # else deficit.output - deficit.demand = (-) load must be shifted
        homes_to_shift = np.ceil(np.abs(unsafe_load) / RES_CONSUMPTION).astype(int)
        surplus['s_net_cap'] = (surplus.output * (1 - SAFETY_THRESHOLD)) - surplus.demand
        deficit['s_net_cap'] = (deficit.output * (1 - SAFETY_THRESHOLD)) - deficit.demand
        surplus['share_of_net'] =  surplus['s_net_cap'] / surplus['s_net_cap'].sum()
        # this breaks when there is only 1 element in the deficit.
        # devide by zero error?
        deficit['share_of_net'] =  deficit['s_net_cap'] / deficit['s_net_cap'].sum()
        surplus['new_load'] = -1 * np.round(
            (surplus['share_of_net'] * unsafe_load) / RES_CONSUMPTION) * RES_CONSUMPTION
        deficit['new_load'] = -1 * surplus['new_load'].sum() * deficit['share_of_net']
        results = pd.concat([surplus,deficit])
        # s = surplus['percent_use'].sort_values(ascending=True)
        with open(LOG_PATH, 'a') as writer:
            writer.write("------------- Load  Balanced -------------\n")
            writer.write("{} generators with energy surplus\n".format(str(len(surplus)).rjust(3)))
            writer.write("{} generators with energy deficit\n".format(str(len(deficit)).rjust(3)))
            writer.write("------------------------------------\n")
            writer.write("   - total capacity was  {:.2f} MW\n".format(df.output.sum()))
            writer.write("   - total demand was    {:.2f} MW\n".format(df.demand.sum()))  
            writer.write("                         ---------\n")
            writer.write("   - spare capacity was  {:.2f} MW    // ignoring safety factor\n".format(
                net_system_cap))
            writer.write("------------------------------------\n")
            writer.write('   - able to shift       {} MW    // considering safety factor\n'.format(
                '{:.1f}'.format(total_safe_capacity).rjust(6)))
            writer.write("------------------------------------\n")
            writer.write("   - 'Safe Load' was     {:.2f} MW    // considering safety factor\n".format(
                safe_load))

            if unsafe_load < 0:
                writer.write("   - 'Unsafe Load' was   {} MW    // need to shift\n".format('({:.1f})'.format(abs(unsafe_load)).rjust(6, " ")))
                writer.write('   - Load shifting to   {} homes // {:,.1f} MW shifted\n'.format('{:,}'.format(homes_to_shift).rjust(7),
                                                                                    abs(surplus.new_load.sum()),abs(surplus.new_load.sum())))

                if total_safe_capacity > np.abs(unsafe_load):
                    writer.write("------------------------------------\n")
                    writer.write("SUCCESS -- load safely shifted\n")
                else:
                    writer.write("------------------------------------\n")
                    writer.write("FAILURE -- load NOT shifted\n")
            else:
                # if   deficit.output - deficit.demand = (+) then no load need be shifted
                writer.write("   - 'Unsafe Load' was        0 MW    \n".format(unsafe_load)) # // {:.2f}
                writer.write("------------------------------------\n")
                writer.write("NO LOAD TO SHIFT\n".center(36))  
            writer.write("------------------------------------\n")
            writer.write('   - Previous Load for {}: {} MW\n'.format(id, previous_load))
            writer.write('   - New Load for      {}: {} MW\n'.format(id, results.loc[id].demand))
            writer.write("------------------------------------\n")
            columns_to_write = ['ts','output','demand','net_cap','percent_use','s_demand','s_net_cap','share_of_net','new_load']
            # writer.write(tabulate(results[columns_to_write], headers='keys', tablefmt='psql'))
            # writer.write('\n')
            return previous_load + results.loc[id].new_load
    else:
        # print('{}.{}: {} returning same demand'.format(id, int(_ts) ,state.loc[id].demand))
        # print(state[['ts','output','demand','percent_use']])
        # print()
        return previous_load


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
        SendGeneratorHello(request)
        return scowl_pb2.Empty()
    
    def UpdateGeneratorState(self, request, context):
        """request is a StateUpdate
        Returns: DemandUpdate:float
        """
        global state # id: ['ts', 'output', 'demand', 'net_cap', 'net_cap_percent']
        safe_net_cap_percent = None # this prevents a division by zero error
        if request.output == 0:
            safe_net_cap_percent = -1.0 # really negative infinity
        else:
            safe_net_cap_percent = (request.output - request.demand) / request.output
        
        wall_clock_time = datetime.datetime.now().isoformat()

        state.loc[request.id] = [
            request.ts,
            HOST_ID,
            TRACKER_ID,
            request.output,
            request.demand,
            request.output - request.demand,
            safe_net_cap_percent,
            wall_clock_time]

        row = '{},{},{},{},{},{},{},{},{}\n'.format(
                request.id,
                request.ts,
                HOST_ID,
                TRACKER_ID,
                request.output,
                request.demand,
                request.output - request.demand,
                safe_net_cap_percent,
                wall_clock_time)

        # print("{} VECTOR CLOCK SIZE: {}\n{}".format(request.id, len(state), state))
        # vector_clock_size = len(state)
        # # print("{}".format(state[state.ts >= state.loc[request.id].ts]))
        # clocks_ahead_of_request = len(state[state.ts >= state.loc[request.id].ts])
        # # print("{} VECTOR UPDATE SIZE: {}".format(len(state), request.id))
        # new_demand = request.demand
        # if vector_clock_size >= clocks_ahead_of_request:
        #     # all clocks are equal to or greater than this one's
        new_demand = LoadBalance(request.id)

        with open(DATA_PATH, 'a') as writer:
            writer.write(row)

        return scowl_pb2.DemandUpdate(demand=new_demand)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scowl_pb2_grpc.add_TrackerServicer_to_server(
        TrackerServicer(), server)
    addr = GetOwnIP() + ':' + str(LISTEN_PORT)
    server.add_insecure_port('[::]:' + str(LISTEN_PORT)) # one higher than Bootstrap server
    server.start()
    start_time = datetime.datetime.now().isoformat()
    print("------------- Tracker Started -------------", )   
    print('Started: ', start_time)
    print('Addr:    ', addr)
    with open(LOG_PATH, "w") as f:
        f.write("------------- Tracker Started -------------\n")
        f.write('Started: {}\n'.format(start_time))
    server.wait_for_termination()


if __name__ == '__main__':
    # TODO: add threading for:
    #   1. Receiving generator bootstrap calls and issuing ACKs to genereators
    print("Tracker {} is responsible for:".format(TRACKER_ID))
    lower, upper = ComputeBucketRange(NUM_BUCKETS, TRACKER_ID, HASH_SIZE) 
    print("IDs [{} , {})".format(lower, upper))
    serve()