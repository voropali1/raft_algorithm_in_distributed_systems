# Manages the heartbeat message sent by the leader.
from messages.base_message import BaseMessage


class HeartbeatMessage(BaseMessage):
    def __init__(self, sender_id, term, prev_log_index, prev_log_term, leader_commit, entries = None):
        """
        Initialize a heartbeat message (which is an empty AppendEntries RPC) from the leader.

        Args:
        - sender_id (str): The ID of the leader sending the heartbeat.
        - term (int): The current term of the leader.
        - prev_log_index (int): The index of the log entry immediately preceding the new entries.
        - prev_log_term (int): The term of the previous log entry.
        - leader_commit (int): The leader's commit index, which is the highest log entry known to be committed.
        """
        super().__init__(term, sender_id)
        self.prev_log_index = prev_log_index
        self.prev_log_term = prev_log_term
        self.leader_commit = leader_commit
        self.entries = entries or []

    def to_dict(self):
        """Convert the HeartbeatMessage to a dictionary."""
        return {
            "sender_id": self.sender_id,
            "term": self.term,
            "prev_log_index": self.prev_log_index,
            "prev_log_term": self.prev_log_term,
            "leader_commit": self.leader_commit,
            "entries": self.entries,
        }
