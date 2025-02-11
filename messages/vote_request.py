# Handles the structure of a request vote message.
from messages.base_message import BaseMessage


class VoteRequestMessage(BaseMessage):
    def __init__(self, sender_id, term, last_log_index, last_log_term):
        """
        Initialize a vote request message from a candidate.

        Args:
        - sender_id (str): The ID of the candidate requesting the vote.
        - term (int): The current term of the candidate.
        - last_log_index (int): The index of the candidate's last log entry.
        - last_log_term (int): The term of the candidate's last log entry.
        """
        super().__init__(sender_id, term)
        self.last_log_index = last_log_index
        self.last_log_term = last_log_term
