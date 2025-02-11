# Contains the specific logic and behavior of a leader node, like sending heartbeats and handling log replication.
import logging
import os
import signal
import time
import requests
import threading
from messages.heartbeat import HeartbeatMessage
from messages.vote_response import VoteResponseMessage
from messages.vote_request import VoteRequestMessage
from flask import Flask, request, jsonify
import sqlite3


class LeaderState:
    def __init__(self, node):
        self.node = node
        self.heartbeat_interval = 1  # Send heartbeats every 1 second
        self.heartbeat_timer = None
        self.next_index = {peer: len(self.node.message_log) for peer in self.node.peers}
        self.match_index = {peer: 0 for peer in self.node.peers}
        self.replication_threshold = 1
        self.last_heartbeat_response = {peer: time.time() for peer in self.node.peers}  
        self.dead_node_timeout = 5
        self.check_interval = 2
        self.failed_heartbeats = {}
        self.max_failed_heartbeats = 5

    def start_leader(self):
        self.send_heartbeats()
        #self.initialize_database()

    def send_heartbeats(self):
        if self.node.running == False and self.node.node_id == self.node.current_leader:
            logging.info(f"[Node {self.node.node_id}] LEADER DIED")
            for node in self.node.get_all_nodes():
                node.current_leader = None
        while self.node.running == False:
            #logging.info(f"[Node {self.node.node_id}] Waiting for node to start running.")
            time.sleep(1) 
            
        for peer in self.node.peers:
            # Construct the heartbeat message
            next_idx = self.next_index.get(peer, 0) 
            prev_log_index = next_idx - 1
            prev_log_term = (
                self.node.message_log[prev_log_index]["term"]
                if prev_log_index >= 0
                else -1
            )
            entries = self.node.message_log[next_idx:]  # Entries to send

            heartbeat_message = HeartbeatMessage(
                sender_id=self.node.node_id,
                term=self.node.current_term,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                leader_commit=self.node.commit_index,
                entries=entries,
            )
            message_dict = heartbeat_message.to_dict()

            # Send the heartbeat to the peer
            try:
                host, port = peer.split(":")
                response = requests.post(
                    f"http://{host}:{port}/append_entries", json=message_dict  
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        self.match_index[peer] = prev_log_index + len(entries)
                        self.next_index[peer] = self.match_index[peer] + 1
                        self.last_heartbeat_response[peer] = time.time()  
                        self.failed_heartbeats[peer] = 0
                        logging.info(
                            f"[Node {self.node.node_id}] Sent heartbeat to {peer}. ++++ {self.node.peers}"
                        )
                    else:
                        self.next_index[peer] -= 1  # Decrement next_index and retry
                        logging.warning(
                            f"[Node {self.node.node_id}] Failed to append entries to {peer}. Reason: {data.get('reason')}"
                        )
                    
                else:
                    logging.warning(
                        f"[Node {self.node.node_id}] Failed to send heartbeat to {peer}. HTTP Status: {response.status_code}"
                    )
                    self.increment_failed_heartbeat(peer)
                    
                    
            except requests.ConnectionError:
                logging.warning(
                    f"[Node {self.node.node_id}] Failed to send heartbeat to {peer}."
                )
                self.increment_failed_heartbeat(peer)
        #self.check_heartbeat_responses()
        # Schedule the next heartbeat
        self.heartbeat_timer = threading.Timer(
            self.heartbeat_interval, self.send_heartbeats
        )
        self.heartbeat_timer.start()
    
    
    def increment_failed_heartbeat(self, peer):
        """Увеличиваем счетчик неудачных попыток для узла"""
        kill_node_address = peer
        if peer not in self.failed_heartbeats:
            self.failed_heartbeats[peer] = 0
        self.failed_heartbeats[peer] += 1

        if self.failed_heartbeats[peer] >= self.max_failed_heartbeats:
            logging.warning(f"[Node {peer}] Peer {peer} failed {self.max_failed_heartbeats} times. Removing from cluster.")
            try:
                logging.info(f"Node  is shutting down...")
                for peer in self.node.peers:
                    try:
                        response = requests.post(f"http://{peer}/remove_node", json={"node_address": kill_node_address}, timeout=10)
                        if response.status_code == 200:
                            logging.info(f"Node  has been removed from peer {peer}.")
                        else:
                            logging.warning(f"Failed to notify peer {peer} about node  removal.")
                    except requests.ConnectionError:
                        logging.warning(f"Could not notify peer {peer} about node removal.")
                if peer in self.node.peers:
                    self.node.peers.remove(kill_node_address)
                    logging.info(f"Node {peer} removed from the cluster.")
                

            except Exception as e:
                logging.error(f"Error stopping the server: {e}")
                
    
    
    def remove(self, peer):
        for node in self.node.get_all_nodes():
                if peer in node.peers: #and node.node_id != number:
                    node.peers.remove(peer)
                node_address = f"{node.hostname}:{node.port}"
                if peer == node_address:
                    node.running = False
           


    def send_append_entries_to_followers(self, message):
        # Append the message to the log with the current term
        self.node.message_log.append(
            {
                "node_id": self.node.node_id,
                "term": self.node.current_term,
                "message": message,
            }
        )

        current_entry_index = len(self.node.message_log) - 1
        success_count = 0

        # Replicate the log entry to followers
        for peer in self.node.peers:
            host, port = peer.split(":")
            url = f"http://{host}:{port}/append_entries"
            prev_log_index = current_entry_index - 1
            prev_log_term = (
                self.node.message_log[prev_log_index]["term"] if prev_log_index >= 0 else -1
            )
            entries = [self.node.message_log[current_entry_index]]

            # Use HeartbeatMessage for consistency
            append_entries_msg = HeartbeatMessage(
                sender_id=self.node.node_id,
                term=self.node.current_term,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                leader_commit=self.node.commit_index,
                entries=entries
            )
            try:
                response = requests.post(url, json=append_entries_msg.to_dict())
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        self.match_index[peer] = current_entry_index
                        success_count += 1
                        logging.info(
                            f"[Node {self.node.node_id}] Successfully replicated entry to {peer}."
                        )
                    else:
                        logging.warning(
                            f"[Node {self.node.node_id}] Failed to replicate entry to {peer}. Reason: {data.get('reason')}"
                        )
                else:
                    logging.warning(
                        f"[Node {self.node.node_id}] Failed to replicate entry to {peer}. HTTP Status: {response.status_code}"
                    )
            except requests.exceptions.RequestException:
                logging.warning(
                    f"[Node {self.node.node_id}] Exception when replicating to {peer}."
                )

        # Check if the majority has acknowledged this entry
        if success_count >= (len(self.node.peers) + 1) // 2:
            # Update commit index
            self.node.commit_index = current_entry_index
            # Save to disk
            


    def stop(self):
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
            self.heartbeat_timer = None

    def vote_request(self):
        data = request.get_json()
        vote_request = VoteRequestMessage.from_dict(data)
        if vote_request.term > self.node.current_term:
            self.node.current_term = vote_request.term
            self.node.become_follower()
            return self.node.current_state.vote_request()
        else:
            response = VoteResponseMessage(
                sender_id=self.node.node_id,
                term=self.node.current_term,
                vote_granted=False,
            )
            return jsonify(response.to_dict()), 200


    def add_new_peer(self, new_peer):

        self.next_index[new_peer] = len(self.node.message_log)
        self.match_index[new_peer] = 0
        logging.info(f"OK")
        
    def remove_peer(self, peer_address):
        if peer_address in self.node.peers:
            self.node.peers.remove(peer_address)
            if peer_address in self.next_index:
                del self.next_index[peer_address]
            if peer_address in self.match_index:
                del self.match_index[peer_address]
            logging.info(f"OK")
            logging.info(f"self.peers: {self.node.peers}")
        elif peer_address == (f"{self.node.hostname}:{self.node.port}"):
            all = self.node.get_all_nodes()
            for peer in all:
                if peer_address in peer.peers:
                    peer.peers.remove(peer_address)
            if peer_address in self.next_index:
                del self.next_index[peer_address]
            if peer_address in self.match_index:
                del self.match_index[peer_address]
            logging.info(f"OK")
        else:
            logging.warning(f"OK")