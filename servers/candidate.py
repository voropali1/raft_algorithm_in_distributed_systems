# candidate.py
import logging
import requests
from threading import Timer
from messages.vote_request import VoteRequestMessage
from messages.vote_response import VoteResponseMessage


class CandidateState:
    def __init__(self, node):
        self.node = node
        self.election_timer = None

    def start(self):
        self.start_election()

    def start_election(self):
        if len(self.node.peers) < 2 and self.node.current_term != 0:
            self.node.become_follower()
            return
        logging.info(f"[Node {self.node.node_id}] Starting election.")
        self.increment_term()
        self.reset_votes()
        self.send_vote_requests()
        self.evaluate_election_result()
        
        #self.start_election_timeout()

    def increment_term(self):
        self.node.current_term += 1

    def reset_votes(self):
        self.node.votes = 1
        self.node.voted_for = self.node.node_id  # Vote for itself

    def send_vote_requests(self):
        last_log_index = len(self.node.message_log) - 1 if len(self.node.message_log) > 0 else -1
        last_log_term = self.node.message_log[last_log_index]["term"] if last_log_index >= 0 else -1

        vote_request = VoteRequestMessage(
            sender_id=self.node.node_id,
            term=self.node.current_term,
            last_log_index=last_log_index,
            last_log_term=last_log_term,
        )
        request_dict = vote_request.to_dict()

        for peer in self.node.peers:
            try:
                host, port = peer.split(":")
                response = requests.post(f"http://{host}:{port}/vote_request", json=request_dict)
                if response.status_code == 200:
                    vote_response = VoteResponseMessage.from_dict(response.json())
                    self.process_vote_response(vote_response, peer)
            except requests.ConnectionError:
                logging.warning(f"[Node {self.node.node_id}] Could not reach {peer} during election.")

    def process_vote_response(self, vote_response, peer):
        if vote_response.vote_granted:
            self.node.votes += 1
        elif vote_response.term > self.node.current_term:
            logging.info(f"[Node {self.node.node_id}] Found newer term from {peer}. Transitioning back to follower.")
            self.node.current_term = vote_response.term
            self.node.become_follower()
            return

    def evaluate_election_result(self):
        if self.node.votes > len(self.node.peers) // 2:
            logging.info(f"[Node {self.node.node_id}] Won the election, transitioning to leader.")
            
            self.node.become_leader()
        else:
            logging.info(f"[Node {self.node.node_id}] Election lost, stepping down to follower.")
            self.node.become_follower()
            
    #def start_election_timeout(self):
    #    
    #    self.election_timer = Timer(self.node.election_timeout, self.handle_election_timeout)
    #    self.election_timer.start()


    #def handle_election_timeout(self):
    #    logging.warning(f"[Node {self.node.node_id}] Election timed out.")
    #    self.start_election()
        
    def stop(self):
        self.node.current_state = None
        if hasattr(self, "retry_election_timer"):
            self.retry_election_timer.cancel()

