import socket 
import threading 
import time
import os
import math
import shutil
import hashlib
import random
import pickle

# Next step is to set up a dict to keep track of which peers have which chunks
# Distribute chunks to peers... randomly?? For each chunk, send it to the folder of peer from 0 to len(peeers). peer[n] can allow is to tie that random number to a peer


peers = {} # List of connected peers
files = {} # List of currently seeded files

# Listening for peers
s = socket.socket() 
s.bind(('127.0.0.1', 8000)) 
s.listen() 
print("Waiting for peers...")

# Interacting with peers
def socket_target(conn,client): 
    while True: 
        # Waiting for message signals from peer
        op_signal = (conn.recv(1024)).decode() 
        if op_signal[0:3] == "OP_": # Operation to quit. Prepare by removing the client and its folders

            if op_signal == "OP_Q": 
                leaving_client = client 
                # Cleanup traces of the disconnecting client
                del peers[leaving_client]
                shutil.rmtree("files/peers/" + leaving_client)
                for j in files:
                    for k in files[j]['chunks']:
                        if client in files[j]['chunks'][k]['seeders']:
                            files[j]['chunks'][k]['seeders'].remove(leaving_client)
                print(leaving_client + " has disconnected. " + str(len(peers)) + " peers on network.")
                op_signal = "OP_NULL"
            if op_signal == "OP_LST": # Lists the files currently shared in the network
        
                string = 'There are currently {} files in the network.\n'.format(len(files))
                i = 0
                for k in files.keys():
                    i += 1
                    string = string + "({}) Name: {}\t Size: {} bytes\n".format(i,k,files[k]['size'])
                conn.send(string.encode())
                op_signal = "OP_NULL"

            if op_signal == "OP_D": # Operation to download.

                # Determine which file the user wants to download
                file_list = pickle.dumps(list(files.keys()))
                conn.send(file_list)
                sig_filename = (conn.recv(1024)).decode()
                
                # Initialize parameters
                chunk_dict = {}
                hash_dict = {}
                peer_dict = {}
                sig_filesize = int(files[sig_filename]['size'])
                
                #For each chunk, identify the peer to serve the chunks then pass necessary parameters to them
                for j in files[sig_filename]['chunks']:
                    chunk = files[sig_filename]['chunks'][j]
                    hash_dict[j] = files[sig_filename]['chunks'][j]['hash']
                    seed_ip = random.choice(chunk['seeders'])
                    seed_conn = peers[seed_ip]
                    seed_ip = seed_ip.split(':')
                    seed_ip = seed_ip[0] + ':' + str(int(seed_ip[1]) + 100)
                    
                    # Keep track of which peers have which chunks
                    if seed_ip in peer_dict.keys():
                        peer_dict[seed_ip].append(j)
                    else:
                        peer_dict[seed_ip] = [j]
                params = pickle.dumps([peer_dict, client, sig_filename, sig_filesize, hash_dict]) #Server IP, Client IP, file, chunk list, peer count, chunk size
                conn.send(params)
                
                # When the client signals that the download has finished, add it to the seeding list
                data = conn.recv(1024).decode()
                if data == "SIG_FIN":
                    for i in files[sig_filename]['chunks']:
                        files[sig_filename]['chunks'][i]['seeders'].append(client)
                op_signal = "OP_NULL"
                
            if op_signal == "OP_LOC": # Prepare and send string containing the relevant information for node listings 
                sig_filename = conn.recv(1024).decode()
                peer_list = list(peers.keys())
                endpoints = {}
                for i in range(1,11):
                    for p in files[sig_filename]['chunks'][i]['seeders']:
                        if p in endpoints:
                            endpoints[p].append(i)
                        else:
                            endpoints[p] = [i]
                data = pickle.dumps(endpoints)
                conn.send(data)
                op_signal = "OP_NULL"
          
            if op_signal == "OP_R": # Operation to request. Get file info, split it into chunks. 
                while True:
                # Find out the file the user wants to download and its size 
                    sig_filename = (conn.recv(1024)).decode() 
                    sig_filesize = (conn.recv(1024)).decode()
                    string = "Registration of " + sig_filename + " of size " + sig_filesize + " bytes successful."
                    conn.send(string.encode())

                # Prepare the parameters for operation
                    try:
                        os.chdir('files/')
                    except:
                        continue 
                    f_in = sig_filename
                    f_in_temp = f_in.split('.')
                    chunk_size = int(math.ceil((int(sig_filesize))/10))
                    f = open(f_in, "rb")
                    split = f.read(chunk_size)
                    if sig_filename not in files: # Write chunk information into dict
                        files[sig_filename] = {"chunks":{},"size":sig_filesize}
                    os.chdir('peers/' + client + '/seeding')

                    # Getting the relevant info for the chunk data
                    for i in range(1,11):
                        # Prepping the registration data for each chunk
                        hashcode = hashlib.sha256(split).hexdigest() 
                        chunk_name = f_in_temp[0] + "_part_" + str(i).zfill(2)

                        # Creating the chunks and registering them
                        os.chdir('../../' + client + '/seeding')
                        with open(chunk_name, "xb") as o: 
                            o.write(split)
                            try:
                                files[sig_filename]['chunks'][i]['seeders'].append(client)   
                            except KeyError:
                                files[sig_filename]["chunks"][i] = {"seeders":[client], "hash":hashcode, "size":chunk_size}
                        split = f.read(chunk_size)
                    os.chdir("../../../../") #resetting the working directory back to root
                    break
            if op_signal == "OP_NULL": # Setting the signal to OP_NULL returns you back to the main loop, allowing you to enter another command
                continue                         
        if not op_signal: 
            break 

# Connecting to peer
while True: 
    conn, address = s.accept()
    client = str(address[0])+":"+str(address[1])
    conn.send(client.encode())
    peers[client] = conn 
    os.makedirs("files/peers/" + client + "/seeding")
    os.makedirs("files/peers/" + client + "/downloading")
    print(client + " has connected. " + str(len(peers)) + " peers on network.")  
    threading.Thread(target=socket_target, args=(conn,client)).start()




