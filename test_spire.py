import sys, argparse
import subprocess
import time
import zipfile
import os

RUN_COMMAND   = "python run_replica.py"
# Script assumes replica is launched with the command:
#     ./run_replica -id [id]
# where [id] is the ID of the server (an integer from 1-NUM_SERVERS)

IMAGE_NAME    = "spire-img"
NETWORK_NAME  = "spire-net"

SERVER_PREFIX = "spire"
NUM_SERVERS   = 4
IP_BASE       = "192.168.101."
# Default IP addresses for the 4 servers are:
#     192.168.101.101
#     192.168.101.102
#     192.168.101.103
#     192.168.101.104
CLIENT_IP     = "192.168.101.107"
CLIENT_NAME   = "spire-client"

log_list = list()

def get_args(argv):
    parser = argparse.ArgumentParser(description="Script for testing Spire")
    subparsers = parser.add_subparsers(required=True, help='available commands')

    parser_init = subparsers.add_parser('init', description='Initialize Docker bridge network and containers')
    parser_init.set_defaults(func=init_all)

    parser_rm = subparsers.add_parser('rm', description='Remove Docker bridge network and containers')
    parser_rm.set_defaults(func=cleanup)

    parser_loss = subparsers.add_parser('loss', description='Set loss rate between two containers')
    parser_loss.add_argument('container1', type=int, help='first container (e.g. 1 for server id 1)')
    parser_loss.add_argument('container2', type=int, help='second container (e.g. 2 for server id 2)')
    parser_loss.add_argument('loss_rate', type=float, help='loss rate to set (e.g. 10.5 adds 10.5%%  loss)')
    parser_loss.set_defaults(func=set_loss)

    parser_part = subparsers.add_parser('partition', description='Create network partitions')
    parser_part.add_argument('partition', nargs='+', help='list of partitions to create. Partitions should be separated by spaces, and servers within each partition should be separated by commas (e.g. "partition 1,2 3,4,5" creates two partitions, one containing servers 1 and 2, and one containing servers 3, 4, and 5")')
    parser_part.set_defaults(func=create_partitions)

    parser_kill = subparsers.add_parser('kill', description='Kill a specific server')
    parser_kill.add_argument('id', type=int, help='ID of server to kill')
    parser_kill.set_defaults(func=kill_server)

    parser_relaunch = subparsers.add_parser('relaunch', description='Re-launch a specific server that was previously killed')
    parser_relaunch.add_argument('id', type=int, help='ID of server to relaunch')
    parser_relaunch.set_defaults(func=relaunch_server)

    parser_client = subparsers.add_parser('benchmark', description='Start benchmark client')
    parser_client.add_argument('n', type=int, help='number of benchmark instances to launch')
    parser_client.set_defaults(func=benchmark)

    parser_client = subparsers.add_parser('loop', description='Start benchmark client on loop')
    parser_client.add_argument('n', type=int, help='number of benchmark instances to launch')
    parser_client.set_defaults(func=benchmark_loop)

    return parser.parse_args()

def benchmark_loop(args):
    # run a couple benchmarks and track how long they take

    average = 0
    max = 0
    print("Running calibration benchmarks")

    for i in range(5):
        run_time = time.time()
        cmd_str = "docker exec {container} python run_benchmark.py -n {num}".format(container=CLIENT_NAME, num=args.n)

        subprocess.run("docker compose up -d", shell=True)
        subprocess.run(cmd_str, shell=True)
        subprocess.run("docker compose down", shell=True)

        run_time = time.time() - run_time
        average += run_time
        if run_time > max:
            max = run_time
        
        print("\n{RUN}/5 :    {TIME} seconds\n".format(RUN=i+1, TIME=run_time))

    average = average / 5
    time_out = average + (max / 20)
    print("Calibration complete - Final timeout: {TIME}\nStarting benchmarks\n".format(TIME=time_out))
    
    while True:
        timeout_err = False
        cmd_str = "docker exec {container} python run_benchmark.py -n {num}".format(container=CLIENT_NAME, num=args.n)
        subprocess.run("docker compose up -d", shell=True)
        print(cmd_str)
        try:
            subprocess.run(cmd_str, shell=True, timeout=time_out)
        except TimeoutError:
            print("Benchmark timed out during run, outputting logs\n")
            timeout_err = True

        spire1 = subprocess.run("docker logs spire1", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        spire2 = subprocess.run("docker logs spire2", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        spire3 = subprocess.run("docker logs spire3", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        spire4 = subprocess.run("docker logs spire4", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        check_logs(timeout_err, spire1.stdout.decode().lower(), spire2.stdout.decode().lower(), spire3.stdout.decode().lower(), spire4.stdout.decode().lower())

        subprocess.run("docker compose down", shell=True)

        #cmd_str = "docker exec {} cd benchmark; ./benchmark id 192.168.101.108:8120  1000000 500 >outputsecond11.txt  2>&1 &".format('HMI')
        #subprocess.run(cmd_str, shell=True)
        #print(cmd_str)

def check_logs(error: bool, s1: str, s2: str, s3: str, s4: str):
    
    error_detected = error

    # spire1 checks paused due to current crashing issues
    # if "... goodbye" in s1:
    #     error_detected = True
    #     print("Error found in spire1, outputting logs")

    if "... goodbye" in s2 or "exit caused by alarm" in s2:
        error_detected = True
        print("Error found in spire2, outputting logs")

    if "... goodbye" in s3 or "exit caused by alarm" in s3:
        error_detected = True
        print("Error found in spire3, outputting logs")

    if "... goodbye" in s4 or "exit caused by alarm" in s4:
        error_detected = True
        print("Error found in spire4, outputting logs")

    if error_detected:
        with open("spire1_output.txt", "w") as text_file:
            print("{}".format(s1), file=text_file)
        with open("spire2_output.txt", "w") as text_file:
            print("{}".format(s2), file=text_file)
        with open("spire3_output.txt", "w") as text_file:
            print("{}".format(s3), file=text_file)
        with open("spire4_output.txt", "w") as text_file:
            print("{}".format(s4), file=text_file)

        subprocess.run("docker cp spire-client:app/spire/out_bench_0.txt .", shell=True)
        compress(["spire1_output.txt", "spire2_output.txt", "spire3_output.txt", "spire4_output.txt", "out_bench_0.txt"])

def compress(file_names):
    print("\nSaving logs to {}.zip\n".format(time.strftime("%m-%d-%Y %H:%M:%S")))

    path = ""

    compression = zipfile.ZIP_DEFLATED

    zf = zipfile.ZipFile(time.strftime("%m-%d-%Y %H:%M:%S"), mode="w")
    try:
        for file_name in file_names:
            zf.write(path + file_name, file_name, compress_type=compression)
        log_list.append(time.strftime("%m-%d-%Y %H:%M:%S"))

    except FileNotFoundError:
        print("An error occurred when zipping logs")
    finally:
        zf.close()

    try:
        for file in file_names:
            os.remove(file)
    except FileNotFoundError:
        print("File missing - check terminal output")

    

def benchmark(args):
    cmd_str = "docker exec {container} python run_benchmark.py -n {num}".format(container=CLIENT_NAME, num=args.n)
    print(cmd_str)
    subprocess.run(cmd_str, shell=True)
    #cmd_str = "docker exec {} cd benchmark; ./benchmark id 192.168.101.108:8120  1000000 500 >outputsecond11.txt  2>&1 &".format('HMI')
    #subprocess.run(cmd_str, shell=True)
    #print(cmd_str)
    
def server_ip(server_id):
    return IP_BASE+str(100+server_id)

def server_name(server_id):
    return SERVER_PREFIX+str(server_id)

# Do all initialization
def init_all(args):
    init_network()
    init_containers()
    time.sleep(10)
    init_netem()

# Create bridge network
def init_network():
    cmd_str = "docker network create --driver bridge --subnet {sub} --gateway {gate} {net}".format(sub=IP_BASE+'0/24', gate=IP_BASE+'1', net=NETWORK_NAME)
    print(cmd_str)
    subprocess.run(cmd_str, shell=True)

# Create containers and attach them to bridge network
def init_containers():
    # start replicas
    for i in range(1,NUM_SERVERS+1):
        cmd_str = "docker run --cap-add=NET_ADMIN --name {serv} --network {net} --ip {ip} {img} {cmd} {args}".format(serv=server_name(i), net=NETWORK_NAME,
        img=IMAGE_NAME, ip=server_ip(i), cmd=RUN_COMMAND, args="-id {} -f 0".format(i))
        print(cmd_str)
        subprocess.Popen(cmd_str, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # start client container
    cmd_str = "docker run --cap-add=NET_ADMIN --name {serv} --network {net} --ip {ip} {img} {cmd}".format(serv=CLIENT_NAME, net=NETWORK_NAME, img=IMAGE_NAME, ip=CLIENT_IP, cmd="python run_client.py")
    print(cmd_str)
    subprocess.Popen(cmd_str, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return

# Initialize netem classes for each server
def init_netem():
    for i in range(1, NUM_SERVERS+1):
        serv_str = server_name(i)

        _init_netem(serv_str)

# Initialize netem such that the given container has a separate traffic class
# for each other server (so that we can manipulate them independently)
def _init_netem(container_name):
    # Set up base class
    cmd_str = "docker exec {} tc qdisc add dev eth0 root handle 1: htb default 10".format(container_name)
    subprocess.run(cmd_str, shell=True)
    cmd_str = "docker exec {} tc class add dev eth0 parent 1: classid 1:1 htb rate 100Mbps".format(container_name)
    subprocess.run(cmd_str, shell=True)
    cmd_str = "docker exec {} tc class add dev eth0 parent 1:1 classid 1:10 htb rate 100Mbps".format(container_name)
    subprocess.run(cmd_str, shell=True)
    cmd_str = "docker exec {} tc qdisc add dev eth0 parent 1:10 handle 10: netem limit 100000 delay 0ms".format(container_name)
    subprocess.run(cmd_str, shell=True)

    # Set up special class per server
    for j in range(1, NUM_SERVERS+1):
        cmd_str = "docker exec {} tc class add dev eth0 parent 1:1 classid 1:{} htb rate 100Mbps".format(container_name, 10+j)
        subprocess.run(cmd_str, shell=True)
    for j in range(1, NUM_SERVERS+1):
        cmd_str = "docker exec {} tc qdisc add dev eth0 parent 1:{} handle {}: netem limit 1000 delay 0ms".format(container_name, 10+j, 10+j)
        #cmd_str = "docker exec {} tc qdisc add dev eth0 parent 1:{} handle {}: netem limit 100000 delay 0ms".format(container_name, 10+j, 10+j)
        subprocess.run(cmd_str, shell=True)
    for j in range(1, NUM_SERVERS+1):
        cmd_str = "docker exec {} tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst {} flowid 1:{}".format(container_name, server_ip(j), 10+j)
        subprocess.run(cmd_str, shell=True)

# Stop all containers, then remove containers and network
def cleanup(args):
    # Stop Servers
    for i in range(1,NUM_SERVERS+1):
        cmd_str = "docker stop {serv}".format(serv=server_name(i))
        subprocess.run(cmd_str, shell=True)

    # Stop Client
    cmd_str = "docker stop {serv}".format(serv=CLIENT_NAME)
    subprocess.run(cmd_str, shell=True)
    
    # Remove Servers
    for i in range(1,NUM_SERVERS+1):
        cmd_str = "docker rm {serv}".format(serv=server_name(i))
        subprocess.run(cmd_str, shell=True)

    # Remove Client
    cmd_str = "docker rm {serv}".format(serv=CLIENT_NAME)
    subprocess.run(cmd_str, shell=True)

    # Remove network
    cmd_str = "docker network rm {net}".format(net=NETWORK_NAME)
    subprocess.run(cmd_str, shell=True)

# Set loss rate between two containers
def set_loss(args):
    id1 = args.container1
    id2 = args.container2
    loss = args.loss_rate
    _set_loss(id1, id2, loss)
    
def _set_loss(id1, id2, loss):
    s1 = server_name(id1)
    s2 = server_name(id2)

    # Set loss outgoing from container1 to container2
    cmd_str1 = "docker exec {} tc qdisc change dev eth0 parent 1:{} handle {}: netem loss {}".format(s1, id2+10, id2+10, loss)
    # Set loss outgoing from container2 to container1
    cmd_str2 = "docker exec {} tc qdisc change dev eth0 parent 1:{} handle {}: netem loss {}".format(s2, id1+10, id1+10, loss)

    # Run commands
    subprocess.run(cmd_str1, shell=True)
    subprocess.run(cmd_str2, shell=True)

# Create partitions (note that this will remove any other loss that was
# previously added)
def create_partitions(args):
    parts = args.partition
    final_parts = []
    for p in parts:
        final_parts.append(p.split(','))

    # Sanity check that all servers are specified
    for i in range(1, NUM_SERVERS+1):
        found = False
        for p in final_parts:
            for s in p:
               if s == str(i):
                found = True
        if not found:
            print("Error: server {} not present in any partition".format(i))
            return

    print(final_parts)

    i = 0
    for part in final_parts:
        i+=1
        # Iterate over each server in the partition, and, for each server in
        # each other partition, set the loss rate to 100% (note that since
        # _set_loss applies loss in both directions, only need to do this for
        # partitions we haven't already handled)
        for server in part:
            for other_part in final_parts[i:]:
                for other_server in other_part:
                    _set_loss(int(server), int(other_server), 100)

    for part in final_parts:
        i = 0
        # For each server in the partition, set loss to each other server in
        # the same partition to 0
        for server in part:
            for other_server in part[i:]:
                _set_loss(int(server), int(other_server), 0)
            i+=1

# Kill a specific server
def kill_server(args):
    s_id = args.id
    s_name = server_name(s_id)

    cmd_str = "docker kill {}".format(s_name)
    subprocess.run(cmd_str, shell=True)

# Relaunch previously killed server
def relaunch_server(args):
    s_id = args.id
    s_name = server_name(s_id)

    cmd_str = "docker start {}".format(s_name)
    subprocess.run(cmd_str, shell=True)

def main(argv):
    args = get_args(argv)
    args.func(args)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        print("User interrupted execution, cleaning up potentially open containers")
        subprocess.run("docker compose down", shell=True)
        print("\nOutput logs: {}".format(log_list))