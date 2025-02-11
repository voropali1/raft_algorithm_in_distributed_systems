import os
import re
import signal
from flask import Flask, app, request, jsonify
import random
import time
import logging

import requests
from servers.follower import FollowerState
from servers.candidate import CandidateState
from servers.leader import LeaderState
import threading


logging.basicConfig(
    level=logging.INFO,  
    format="[%(asctime)s] %(levelname)s - %(message)s",
)

#app = Flask(__name__)  
all_nodes=[]
lock = threading.Lock()
is_candidate = False

class Node:
    is_leader = False
    def __init__(self, node_id, hostname, port, peers=None, is_first = None):
        self.node_id = node_id
        self.current_leader = None
        self.hostname = hostname
        self.port = port
        self.running = False
        self.is_candidate = False
        self.app = Flask(__name__)
        self.is_leader = False
        self.message_log = []
        self.value = None
        self.election_timer = None
        self.election_timeout = random.uniform(8, 12)
        self.state = "Follower"
        self.start_elections = False
        self.current_term = 0
        self.server_thread = None
        self.commit_index = 0
        self.current_state = None
        self.container_name = f"raft-consensus-python-node{node_id}-1"
        self.peers = peers if peers else ()  
        self.list_with_address = []
        if is_first == True:
            self.is_first = is_first
            logging.info(f"[Node {self.node_id}] is the first node in the cluster.")
        else:
            logging.info(f"[Node {self.node_id}] is NOT the first node in the cluster.")
            self.is_first = False
        self.start_node()
        all_nodes.append(self)
        self.flag = 1
        

        # Define API endpoints
        self.app.add_url_rule("/receive_message", "receive_message", self.receive_message, methods=["POST"])
        self.app.add_url_rule("/send_message", "send_message", self.send_message, methods=["POST"])
        self.app.add_url_rule("/message_log", "get_message_log", self.get_message_log, methods=["GET"])
        self.app.add_url_rule("/status", "status", self.status, methods=["GET"])
        self.app.add_url_rule("/append_entries", "append_entries", self.append_entries, methods=["POST"])
        self.app.add_url_rule("/vote_request", "vote_request", self.vote_request, methods=["POST"])
        self.app.add_url_rule("/client_request", "client_request", self.client_request, methods=["POST"])
        self.app.add_url_rule("/leave", "leave", self.leave, methods=["POST"])
        self.app.add_url_rule("/stop_node", "stop_node", self.stop_node, methods=["POST"])  
        self.app.add_url_rule("/stop", "stop", self.stop, methods=["POST"]) 
        self.app.add_url_rule("/remove_node", "remove_node", self.remove_node, methods=["POST"])  
        self.app.add_url_rule("/kill", "kill", self.kill, methods=["POST"])  
        self.app.add_url_rule("/shutdown", "shutdown", self.shutdown, methods=["POST"])
        self.app.add_url_rule("/join", "join", self.join, methods=["POST"])  
        self.app.add_url_rule("/get_leader", "get_leader", self.get_leader, methods=["GET"])
        self.app.add_url_rule("/initialize_from_request", "initialize_from_request", self.initialize_from_request, methods=["POST"])  
        self.app.add_url_rule("/update_peers", "update_peers", self.update_peers, methods=["POST"]) 
        self.app.add_url_rule("/restart_server", "restart_server", self.restart_server, methods=["POST"])
        self.app.add_url_rule("/set_value", "set_value", self.set_value, methods=["POST"])
        self.app.add_url_rule("/get_value", "get_value", self.get_value, methods=["GET"])
        

    def to_dict(self):
        return {
            'node_id': self.node_id,
            'current_leader': self.current_leader,
            'hostname': self.hostname,
            'port': self.port,
            'running': self.running,
            'is_candidate': self.is_candidate,
            'is_leader': self.is_leader,
            'message_log': self.message_log,
            'election_timeout': self.election_timeout,
            'state': self.state,
            'start_elections': self.start_elections,
            'current_term': self.current_term,
            'commit_index': self.commit_index,
            'current_state': self.current_state,
            'container_name': self.container_name,
            'peers': self.peers,
            'is_first': self.is_first,
            'list_with_address': self.list_with_address
        }
    
        
    def status(self):
        try:
            status = {
                "node_id": self.node_id,
                "state": self.state, 
                "current_term": self.current_term,  
                "voted_for": self.voted_for,  
                "is_candidate": self.is_candidate 
            }
            return status
        except Exception as e:
            logging.error(f"Failed to get status for node {self.node_id}: {e}")
            return {"error": f"Unable to fetch status: {str(e)}"}

    
        
    def initialize(self, peers=None, leader=None):
        if peers is not None:
            self.peers = peers
            self.current_leader = leader

            if leader is not None:
                self.state = "Follower"
                self.current_state = FollowerState(self)
                self.is_leader = False
                self.become_follower()
                logging.info(f"[Node {self.node_id}] Initialized as follower of leader {leader}. Peers: {self.peers}")
            else:
                self.state = "Candidate"
                self.start_elections = True
                self.is_candidate = True
                self.become_candidate()
                logging.info(f"[Node {self.node_id}] No leader found, starting elections.")

        elif len(self.peers) == 0 and self.is_first:
            self.state = "Leader"
            self.current_state = LeaderState(self)
            self.is_leader = True
            self.current_leader = self.node_id
            self.become_leader()
            logging.info(f"[Node {self.node_id}] I am the first node, becoming the leader.")

        else:
            leader_id = self.get_leader_from_cluster()
            if leader_id is not None:
                self.state = "Follower"
                self.current_state = FollowerState(self)
                self.is_leader = False
                self.current_leader = leader_id
                self.become_follower()
                logging.info(f"[Node {self.node_id}] Became a follower of leader {leader_id}.")
            else:
                self.state = "Candidate"
                self.start_elections = True
                self.is_candidate = True
                self.become_candidate()
                logging.info(f"[Node {self.node_id}] No leader found, starting elections.")


    def initialize_from_request(self):
        data = request.json  
        if not data:
            logging.error("No data received for initialization") 
            return "Bad Request: No data received", 400

        peers = data.get('peers')
        leader = data.get('leader')
        if peers is None or leader is None:
            logging.error("Missing 'peers' or 'leader' in initialization data")
            return "Bad Request: Missing 'peers' or 'leader'", 400

        try:
            self.initialize(peers=peers, leader=leader)
            return "Node initialized successfully", 200
        except Exception as e:
            logging.error(f"Failed to initialize node: {e}")
            return "Internal Server Error", 500


  
    def set_value(self):
        if self.current_state.__class__.__name__ != "LeaderState":
            return jsonify({"error": "Only the leader can set the value."}), 403

        data = request.get_json()
        new_value = data.get("value")
        if new_value is None:
            return jsonify({"error": "No value provided."}), 400
        self.value = new_value

        self.current_state.send_append_entries_to_followers(new_value)

        return jsonify({"message": "Value set and propagated.", "value": new_value}), 200


    
    def get_value(self):
        return jsonify(self.message_log[-1]), 200


        

    def start_node(self):
        
        self.server_thread = threading.Thread(target=self.run_flask_server)
        self.server_thread.start()
        self.running = True
        time.sleep(1)
        if self.is_first:
            self.is_first = False
            self.initialize()
        
        
    def start_node_repeat(self):
        self.running = True
        logging.info(f"[Node {self.node_id}] ONNNN.")
        logging.info(f"[Node {self.node_id}] {self.state} {self.current_state}")
        time.sleep(1)
        self.initialize()
        return jsonify({"status": "Node ONNNN"}), 200
        
    def stop_node1(self):
        self.state = "Follower"
        self.current_term = 0
        self.server_thread = None
        self.commit_index = 0
        self.current_state = FollowerState(self)
        self.running=False
        logging.info(f"[Node {self.node_id}] Shutting down node.")
        return jsonify({"status": "Node stopped"}), 200
    
    def stop(self):

        if self.server_thread:
            logging.info(f"[Node {self.node_id}] Stopping Flask server...")
            self.flag = 0
            os.kill(os.getpid(), signal.SIGINT)
            self.server_thread.join() 
            logging.info(f"[Node {self.node_id}] Flask server stopped.")
        else:
            logging.warning(f"[Node {self.node_id}] No server thread to stop.")

        return jsonify({"status": "Node stopped"}), 200

    
    
    

    def stop_node(self):
        """
        Этот метод будет вызван при отправке POST-запроса на остановку текущего узла.
        """
        data = request.get_json()
        target_node_id = data.get("node_id") 

        if not target_node_id:
            return jsonify({"error": "Node ID is required to stop a node."}), 400

        target_node = self.get_node_by_id1(target_node_id)
        if not target_node:
            return jsonify({"error": f"Node with ID {target_node_id} not found."}), 404

        try:
            stop_response = requests.post(
                f"http://{target_node.hostname}:{target_node.port}/stop",  
                timeout=5
            )
            if stop_response.status_code == 200:
                logging.info(f"Successfully sent stop request to Node {target_node_id}.")
                return jsonify({"status": f"Node {target_node_id} stopped successfully."}), 200
            else:
                return jsonify({"error": f"Failed to stop Node {target_node_id}."}), 500
        except Exception as e:
            logging.error(f"Error sending stop request to Node {target_node_id}: {e}")
            return jsonify({"error": "Error occurred while sending stop request."}), 500

    def get_node_by_id1(self, node_id):
        for node in all_nodes:
            if node.node_id == node_id:
                return node
        return None


    def run_flask_server(self):
        try:
            logging.info(f"[Node {self.node_id}] Starting Flask server on {self.hostname}:{self.port}")
            self.app.run(host=self.hostname, port=self.port, threaded=True)
        except Exception as e:
            logging.error(f"Server error: {e}")
           
    def restart_server(self):
        """
        Перезапускает сервер, если он был остановлен.
        """
        logging.info(f"[Node {self.node_id}] Restarting Flask server...")
        self.stop()  
        self.server_thread = threading.Thread(target=self.start_server) 
        self.flag = 1
        self.server_thread.start()  

        return jsonify({"status": "Node restarted"}), 200
    
    
    
    
    def shutdown(self):
        """Останавливает сервер"""
        os.kill(os.getpid(), signal.SIGINT) 
        return 'Server shutting down...'
    
    def become_follower(self, term=None):
        if self.current_state and hasattr(self.current_state, "stop"):
            logging.info(f"[Node {self.node_id}] has current state")
            self.current_state.stop()
        self.state = "Follower"
        self.current_state = FollowerState(self)
        if term is not None:
            self.current_term = term
            logging.info(f"[Node {self.node_id}] [{self.current_leader}]")
            self.is_leader = False
        logging.info(f"[Node {self.node_id}] Transitioned to Follower state.")
        self.current_state.initialize()
        

    def become_candidate(self):
        if self.current_state and hasattr(self.current_state, "stop"):
            self.current_state.stop()
        self.state = "Candidate"
        self.current_state = CandidateState(self)
        self.is_candidate = True
        logging.info(f"[Node {self.node_id}] Transitioned to Candidate state.")
        self.current_state.start()
        
    def reset_candidate(self):
        
        Node.is_candidate = False
        logging.info(f"[Node {self.node_id}] OK")

    def become_leader(self):
        
        if self.current_state and hasattr(self.current_state, "stop"):
            self.current_state.stop()
        self.state = "Leader"
        self.current_state = LeaderState(self)
        self.is_leader = True
        self.is_candidate = False
        logging.info(f"[Node {self.node_id}] Transitioned to Leader state.")
        if self.node_id == 1:
            self.current_state.add_new_peer(self)
            self.is_candidate = False
        for peer in Node.get_all_nodes():
            if peer.current_leader == None:
                peer.current_leader = self.node_id
        self.current_state.start_leader()

    def convert_peers(self, peer, flag):
        if flag ==0 and peer not in self.list_with_address:
            self.list_with_address.append(peer)
        if flag == 1 and peer in self.list_with_address:
            self.list_with_address.remove(peer)
        new_peers = []
        host, port = peer.split(":")
        node_id = int(port) - 1999 
        node_name = f"node{node_id}"
        new_peers.append(f"{node_name}:{port}")
        logging.info(f"Converted peer {peer} to {node_name}:{port}")

        return new_peers



    def receive_message(self):
        data = request.get_json()
        sender = data.get("sender")
        message = data.get("message")
        self.message_log.append((sender, message))
        logging.info(f"[Node {self.node_id}] Received message from Node {sender}: {message}")
        return jsonify({"status": "Message received"}), 200

    def send_message(self, message):
        logging.info(f"[Node {self.node_id}] Sending message: {message}")
        if self.state == "Leader":
            pass
        return jsonify({"status": "Message sent"}), 200

    def get_message_log(self):
        return jsonify({"messages": self.message_log}), 200

    def get_state(self):
        return jsonify({"state": self.state, "node_id": self.node_id}), 200

    def append_entries(self):
        if self.current_state is not None:
            return self.current_state.append_entries()
        else:
            return jsonify({"success": True}), 200

    def vote_request(self):
        
        return self.current_state.vote_request()

    def process_client_request(self, message):
        self.current_state.send_append_entries_to_followers(message)

    def client_request(self):
        data = request.get_json()
        message = data.get('message')
        logging.info(f"Leader [Node{self.node_id}] received a client request")
        if self.state != 'Leader':
            return jsonify({'error': 'Not the leader, leader unknown'}), 400
        else:
            self.process_client_request(message)
            return jsonify({'status': 'Message received and replicated'}), 200  
    
    @staticmethod
    def get_all_nodes():
        with lock:
            return all_nodes
    
   
    
    
    
    def join(self):
        new_node = request.json
        new_node_hostname = new_node.get('hostname')
        new_node_port = new_node.get('port')
        new_node_id = new_node.get('node_id')
        new_node_address = f"{new_node_hostname}:{new_node_port}"
        self.peers = list(self.peers) 
        logging.info(f"Node {new_node_id} is trying to join the cluster")
        self.peers.append(f"{new_node_hostname}:{new_node_port}")
        peers_for_new = list()
        for peer in self.peers:
            if new_node_address != peer:
                peers_for_new.append(peer)
        old_node_address = f"{self.hostname}:{self.port}"
        peers_for_new.append(old_node_address)
        response = {
            'message': 'Successfully joined the cluster',
            'peers': peers_for_new,
            #'all_nodes': [node.to_dict() for node in Node.get_all_nodes()]
        }


        logging.info(f"Node {new_node_id} joined successfully. Current peers: {peers_for_new}")
        
        try:
            init_response = requests.post(
                f"http://{new_node_address}/initialize_from_request",
                json={'peers': peers_for_new, 'leader': self.node_id},
                timeout=5
            )
            if init_response.status_code == 200:
                logging.info(f"Node {new_node_id} initialized successfully")
            else:
                logging.warning(f"Failed to initialize node {new_node_id}: {init_response.text}")
        except Exception as e:
            logging.error(f"Error initializing node {new_node_id}: {e}")

        peers_for_update= list()
        for peer in self.peers:
            peers_for_update.append(peer)
        old_node_address = f"{self.hostname}:{self.port}"
        peers_for_update.append(old_node_address)
        
        for peer in self.peers:
            if peer != new_node_address: 
                try:
                    update_response = requests.post(
                        f"http://{peer}/update_peers",
                        json={'peers': peers_for_update},
                        timeout=5
                    )
                    if update_response.status_code == 200:
                        logging.info(f"Updated peer {peer} with new cluster information.")
                    else:
                        logging.warning(f"Failed to update peer {peer}: {update_response.text}")
                except Exception as e:
                    logging.error(f"Error notifying peer {peer} about updated cluster: {e}")
        
        return jsonify(response), 200    
    

    def leave(self):
    
        leaving_node = request.json
        leaving_node_hostname = leaving_node.get('hostname')
        leaving_node_port = leaving_node.get('port')
        leaving_node_id = leaving_node.get('node_id')
        leaving_node_address = f"{leaving_node_hostname}:{leaving_node_port}"

        if leaving_node_address not in self.peers:
            logging.warning(f"Node {leaving_node_id} is not part of the cluster.")
            return jsonify({'message': 'Node not part of the cluster'}), 400

        for peer in self.peers:
            if peer == leaving_node_address:
                try:
                    kill_url = f"http://{leaving_node_hostname}:{leaving_node_port}/kill"
                    kill_response = requests.post(kill_url, timeout=5)
                    if kill_response.status_code == 200:
                        logging.info("Kill request successful. Server shutting down.")
                    else:
                        logging.error(f"Kill request failed: {kill_response.text}")
                except Exception as e:
                    logging.error(f"Error sending kill request: {e}")
        self.peers = [peer for peer in self.peers if peer != leaving_node_address]
        logging.info(f"Node {leaving_node_id} is leaving the cluster. Updated peers: {self.peers}")

        if self.state == "Leader":
            for peer in self.peers:
                try:
                    leave_notify_response = requests.post(
                        f"http://{peer}/update_peers",
                        json={'peers': self.peers},
                        timeout=5
                    )
                    if leave_notify_response.status_code == 200:
                        logging.info(f"Updated peer {peer} with new cluster information.")
                    else:
                        logging.warning(f"Failed to update peer {peer}: {leave_notify_response.text}")
                except Exception as e:
                    logging.error(f"Error notifying peer {peer} about updated cluster: {e}")
        
        response = {
            'message': f"Node {leaving_node_id} successfully left the cluster",
            'updated_peers': self.peers
        }

        return jsonify(response), 200
    
    
    def kill(self):
        kill_node_address = f"{self.hostname}:{self.port}"
        try:
            logging.info(f"Node {self.node_id} is shutting down...")
            for peer in self.peers:
                try:
                    response = requests.post(f"http://{peer}/remove_node", json={"node_address": kill_node_address}, timeout=10)
                    if response.status_code == 200:
                        logging.info(f"Node {self.node_id} has been removed from peer {peer}.")
                    else:
                        logging.warning(f"Failed to notify peer {peer} about node {self.node_id} removal.")
                except requests.ConnectionError:
                    logging.warning(f"Could not notify peer {peer} about node {self.node_id} removal.")
            os.kill(os.getpid(), signal.SIGINT)
            logging.info("Server has been stopped.")
            return jsonify({"status": "Server is shutting down..."}), 200

        except Exception as e:
            logging.error(f"Error stopping the server: {e}")
            return jsonify({"error": f"Failed to stop the server: {e}"}), 500

    def remove_node(self):
        logging.info(f"Node {self.node_id} has peers {self.peers}")
        try:
            data = request.json
            node_address = data.get("node_address")
            
            if not node_address:
                logging.error("Node address not provided in request.")
                return jsonify({"error": "Node address is required"}), 400
            
            if node_address in self.peers:
                self.peers = [peer for peer in self.peers if peer != node_address]
                logging.info(f"Node {node_address} has been removed from the peers list.")
                return jsonify({"status": f"Node {node_address} successfully removed from peers."}), 200
            else:
                logging.warning(f"OK")
                return jsonify({"error": f"Node {node_address} not found in peers list."}), 400
        except Exception as e:
            logging.error(f"Error removing node: {e}")
            return jsonify({"error": f"Error removing node: {e}"}), 500

    def update_peers(self):
        data = request.json
        if not data:
            logging.error("No data received for updating peers")
            return jsonify({"error": "No data received"}), 400
        
        updated_peers = data.get('peers') 
        for peer in updated_peers:
            if peer != f"{self.hostname}:{self.port}" and peer not in self.peers:
                self.peers.append(peer)
        if updated_peers is None:
            logging.error("Peers data is missing")
            return jsonify({"error": "Peers data is missing"}), 400

        logging.info(f"[Node {self.node_id}] Peers list updated: {self.peers}")
        return jsonify({"message": "Peers updated successfully", "peers": self.peers}), 200
    
        
        
    
    def remove_peer(self):
        data = request.get_json()
        peer = data.get("peer")
        if peer in self.peers:
            self.peers.remove(peer)
            logging.info(f"[Node {self.node_id}] Peer {peer} removed from the cluster.")
            return jsonify({"status": f"Peer {peer} removed from the cluster."}), 200
        else:
            return jsonify({"error": f"Peer {peer} not found in the cluster."}), 400

    
    def get_leader(self):
        if self.is_leader:
            return jsonify({"leader_id": self.node_id, "state": self.state}), 200
        else:
            leader_node = self.find_leader() 
            if leader_node is not None:  
                return jsonify({"leader_id": leader_node.node_id, "state": leader_node.state}), 200
            else:
                logging.warning(f"[Node {self.node_id}] No leader found in the cluster.")
                return jsonify({"error": "No leader found"}), 404


    def find_leader(self):
        for peer in self.peers:
            peer_host, peer_port = peer.split(':')
            try:
                response = requests.get(f"http://{peer_host}:{peer_port}/get_leader")
                if response.status_code == 200:
                    leader_data = response.json()
                    if leader_data["state"] == "Leader":
                        return self.get_node_by_id(leader_data["leader_id"])
            except requests.exceptions.RequestException:
                continue
        return None 

    def get_node_by_id(self, node_id):
        for peer in self.peers:
            peer_host, peer_port = peer.split(':')
            node_id = int(peer_port) - 1999
            if peer.node_id == node_id:  
                return peer
        return None  

    def get_leader_from_cluster(self):
        for peer in self.peers:
            peer_host, peer_port = peer.split(':')
            response = requests.get(f"http://{peer_host}:{peer_port}/get_leader")
            if response.status_code == 200:
                leader_data = response.json()
                leader_node = self.get_node_by_id(leader_data["leader_id"])  
                if leader_node is not None:
                    return leader_node.node_id
        return None  

    def add_node(node):
        with lock:
            all_nodes.append(node)
