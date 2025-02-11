# Defines behavior specific to a follower, like receiving heartbeats and responding to vote requests.
from threading import Timer
import logging
import time

import requests
from messages.heartbeat import HeartbeatMessage
from messages.vote_request import VoteRequestMessage
from messages.vote_response import VoteResponseMessage
from flask import request, jsonify
logging.basicConfig(
    level=logging.INFO,  
    format="[%(asctime)s] %(levelname)s - %(message)s",
)

class FollowerState:
    def __init__(self, node):
        self.node = node
        self.candidate = False
        self.last_heartbeat_time = time.time() 
        self.dead_node_timeout = 5

    def start(self):
        # No additional action needed when starting as a follower
        pass

    def stop(self):
        # Stop election timer or other tasks specific to follower state
        if self.node.election_timer:
            self.node.election_timer.cancel()
        logging.info(f"[Node {self.node.node_id}] Stopped Follower state.")

    def initialize(self):
        self.reset_election_timer()

    def reset_election_timer(self):
        self.last_heartbeat_time = time.time()
        if self.node.election_timer:
            self.node.election_timer.cancel()
        self.node.election_timer = Timer(self.node.election_timeout, self.start_election)  # Remove parentheses
        self.node.election_timer.start()


    def start_election(self):
        existing_candidate = False
        for peer in self.node.peers:
            try:
                response = requests.get(f"http://{peer}/status", timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("state") == "Candidate" or data.get("state") == "Leader":
                        existing_candidate = True
                        break
            except requests.ConnectionError:
                logging.warning(f"[Node {self.node.node_id}] Could not check status of peer {peer}. Skipping.")


        if existing_candidate:
            logging.info(f"[Node  Cannot become candidate, another node is already a candidate.")
            #self.become_follower()
            return
        logging.info(f"[Node {self.node.node_id}] No leader detected, starting election.")
        #self.node.state = "Candidate"
        self.node.become_candidate()
        
        
    def append_entries(self):
        data = request.get_json()
        heartbeat = HeartbeatMessage.from_dict(data)

        # Validate the term and update the state if necessary
        if heartbeat.term < self.node.current_term:
            return jsonify({"success": False, "reason": "Outdated term"}), 200

        # Update current term if heartbeat term is higher
        if heartbeat.term > self.node.current_term:
            self.node.current_term = heartbeat.term
            self.node.voted_for = None  # Reset voted_for when term changes

        # Record the leader ID
        self.node.leader_id = heartbeat.sender_id
        self.node.current_id = heartbeat.sender_id

        # Reset election timer upon receiving a valid heartbeat
        logging.info(f"[Node {self.node.node_id}] Received heartbeat from leader {heartbeat.sender_id}, peers:{self.node.peers}.")
        self.last_heartbeat_time = time.time()
        self.reset_election_timer()

        # Append any new entries
        entries = data.get('entries', [])
        prev_log_index = data.get('prev_log_index', -1)
        prev_log_term = data.get('prev_log_term', -1)

        # Case 1: `prev_log_index` is beyond the bounds of the follower's log
        # This means the follower's log is shorter than expected, so reject the append request
        if prev_log_index >= len(self.node.message_log):
            return jsonify({"success": False, "reason": "Log inconsistency: missing entries"}), 200

        # Case 2: `prev_log_index` is within bounds, but the term at `prev_log_index` does not match
        if prev_log_index >= 0 and self.node.message_log[prev_log_index]['term'] != prev_log_term:
            return jsonify({"success": False, "reason": "Log inconsistency: term mismatch"}), 200

        # Append new entries
        if entries:
            # Remove conflicting entries and append new ones
            self.node.message_log = self.node.message_log[:prev_log_index+1]
            self.node.message_log.extend(entries)
            #self.node.value = 
            logging.info(
                f"[Node {self.node.node_id}] appended entries to log. Last appended entry: {self.node.message_log[-1]}"
            )

        # Update commit index
        leader_commit = data.get('leader_commit', self.node.commit_index)
        if leader_commit > self.node.commit_index:
            self.node.commit_index = min(leader_commit, len(self.node.message_log) - 1)
            logging.info(
                f"[Node {self.node.node_id}] updated commit index to {self.node.commit_index}."
            )
        
        return jsonify({"success": True}), 200
    
    
    def remove_dead_node(self, peer_address):
        logging.info(f"{self.node.node_id}{self.node.peers} +++++ {peer_address}")
        if peer_address in self.node.peers:
            self.peers.remove(peer_address)
            logging.info(f"[Node {self.node_id}] Node {peer_address} removed from peers. Peer timeout.")
            
    def remove(self, peer):
        for node in self.node.get_all_nodes():
                # Проверяем, есть ли peer уже в списке peers узла
                if peer in node.peers: #and node.node_id != number:
                    node.peers.remove(peer)
        
    def vote_request(self):
        if self.node.running == True:
            """
            Endpoint to handle VoteRequest RPC from a candidate.
            """
            data = request.get_json()
            vote_request = VoteRequestMessage.from_dict(data)

            # Check the term and candidate eligibility
            if vote_request.term < self.node.current_term:
                # Reject vote request due to outdated term
                response = VoteResponseMessage(
                    sender_id=self.node.node_id, term=self.node.current_term, vote_granted=False
                )
                return jsonify(response.to_dict()), 200

            # Update term if the candidate's term is higher
            if vote_request.term > self.node.current_term:
                self.node.current_term = vote_request.term
                self.node.voted_for = None  # Reset voted_for when term changes

            # Grant vote if this node hasn't voted yet or is voting for the same candidate
            if self.node.voted_for is None or self.node.voted_for == vote_request.sender_id:
                logging.info(
                    f"[Node {self.node.node_id}] Voting for candidate {vote_request.sender_id} in term {vote_request.term}."
                )
                self.node.voted_for = vote_request.sender_id
                self.reset_election_timer()
                response = VoteResponseMessage(
                    sender_id=self.node.node_id, term=self.node.current_term, vote_granted=True
                )
                return jsonify(response.to_dict()), 200

            # Otherwise, do not grant the vote
            response = VoteResponseMessage(
                sender_id=self.node.node_id, term=self.node.current_term, vote_granted=False
            )
            return jsonify(response.to_dict()), 200
