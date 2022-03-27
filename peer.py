import socket 
import os
import time
import pickle
import threading
import hashlib
import math
import glob
import shutil

# Ready sockets and starting conditions
os.chdir('files/')
s = socket.socket()
peers = {}
srv = socket.socket()
s.connect(('127.0.0.1', 8000))

# Retrieving own address, and converting into usable parameters
address = s.recv(1024).decode().split(':')
address[1] = int(address[1])


# Handles user input
def command_prompt():
    while True: 
        command = input('P2P File Sharing Service\n---------\nEnter a command:\n') 
        if command == "q":  # Command to quit
            print("Exiting...")
            data = "OP_Q" # Sends signal to server notifying it of the disconnection
            s.send(data.encode())
            os._exit(1)
        if command == "r":
            data = "OP_R" # Signals to the server that this is a register command
            s.send(data.encode())
            filename = input("What file would you like to share?\n")
            if os.path.isfile(filename):
                s.send(filename.encode())
                size = os.path.getsize(filename)
                time.sleep(2)
                s.send(str(size).encode())
                print(s.recv(1024).decode())
            else:
                print("Filename not valid.")
        if command == "lst":  # Command to list registered files
            data = "OP_LST" # Sends signal to server notifying it of the disconnection
            s.send(data.encode())
            print(s.recv(1024).decode())
        if command == "loc": 
            # With a filename as input, the server returns each seeder and its respective chunks
            data = "OP_LOC"
            s.send(data.encode())
            filename = input("What file would you like to check?\n")
            if os.path.isfile(filename):
                s.send(filename.encode())
                data = s.recv(1024)
                endpoints = pickle.loads(data)
                # Taking the information from the dict and printing it as the location info
                print("There are {} endpoints seeding this file.".format(len(endpoints)))
                for i in endpoints:
                    print("Peer {} currently has chunks {}.".format(i,endpoints[i]))
            else:
                print("Filename not valid.")
        if command == "d":
            data ="OP_D"
            s.send(data.encode())
            
            # Display list of registered files to user
            file_list = pickle.loads(s.recv(1024))
            print("The following files are currently registered:")
            for i in file_list:
                print(i+"\n")

            # Ask user for file to download, then process file information supplied by server
            filename = input("What file would you like to download?\n")
            if os.path.isfile(filename):
                s.send(filename.encode())
            else:
                print("Filename not valid.")
            data = s.recv(1024) 
            params = pickle.loads(data)
            peer_list = list(params[0].keys())
            chunk_list = list(params[0].values())[0] 
            client = params[1]
            peer_count = len(peer_list)
            chunk_size = int(math.ceil((int(params[3]))/10))
            chunks = {}
            hash_dict = params[4]
            error_flag = 0

            # For every peer you're seeding from, ready a connection
            for p in peer_list:
                peers[p] = socket.socket()
                peer_ip = p.split(':')
                peers[p].connect((peer_ip[0],int(peer_ip[1])))
                peers[p].send(data)
                
            # For every peer you're seeding from, get the chunks they send
            for c in range(1,11):
                for p in peer_list:
                    if c in params[0][p]:# CHeck                   
                        tmp = peers[p].recv(chunk_size)
                        hashcode = hashlib.sha256(tmp).hexdigest() 
                        if hashcode != hash_dict[c]:
                            print("Error downloading chunk " + str(c) + ' from ' + p + ", try again.")
                            error_flag = 1
                        else:
                            chunks[c] = tmp
                            print("Recieved chunk " + str(c) + " from " + p)
                    else:
                        continue             

            # Download files
            for c in chunks:
                src = 'peers/' + client + '/downloading/' + filename.split('.')[0] + '_part_' + str(c).zfill(2)
                f = open(src, 'xb')
                f.write(chunks[c])
                
            # Seed each file as it is being downloaded
                dst = 'peers/' + client + '/seeding/' + filename.split('.')[0] + '_part_' + str(c).zfill(2)
                shutil.copyfile(src,dst)
                f.close()
                                
            # When all chunks are downloaded, merge them into a full file
            chunk_merge = sorted(glob.glob('peers/' + client + '/downloading/' + filename.split('.')[0]+'*'))
            with open('peers/' + client + '/downloading/' + filename, 'xb') as o:
                for f in chunk_merge:
                    with open(f,'rb') as i:
                        o.write(i.read())

            # Let user and server know downloading is complete
            print(filename + " has completed downloading.")
            for f in chunk_merge:
                os.remove(f)
            s.send("SIG_FIN".encode())

# Handles file download requests from other peers
def peer_serve():    
        # Creating server on first port available for p2p sharing
        srv.bind((address[0],address[1]+100))
        srv.listen()
        while True:
            # Connect upon download request
            conn, addr = srv.accept()
            data = conn.recv(1024)
            params = pickle.loads(data)

            # Unpack parameters for operation
            address_string = address[0] + ':' + str(address[1])
            address_string_srv = address[0] + ':' + str(address[1]+100)

            chunk = params[0]
            chunk_list = params[0][address_string_srv]
            chunk_list_srv = chunk[address_string_srv]
            chunk_size = int(math.ceil((int(params[3]))/10))

            leech_ip = params[1]
            filename = params[2].split('.')[0]

            # Send file back to peer
            for j in chunk_list:
                src = 'peers/' + address_string + '/seeding/' + filename + '_part_' + str(j).zfill(2)
                f = open(src, 'rb')
                chunk_read = f.read(chunk_size)
                conn.send(chunk_read)
                

# Start user-input and seeding on separate threads
serveThread = threading.Thread(target=peer_serve, args=()).start()
commandThread = threading.Thread(target=command_prompt, args=()).start()
