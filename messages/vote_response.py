#  Manages the response format for vote requests.
from messages.base_message import BaseMessage


class VoteResponseMessage(BaseMessage):
    def __init__(self, sender_id, term, vote_granted):
        """
        Initialize a vote response message to respond to a candidate's vote request.

        Args:
        - sender_id (str): The ID of the node sending the response.
        - term (int): The current term of the responding node.
        - vote_granted (bool): Boolean indicating whether the vote was granted or not.
        """
        super().__init__(sender_id, term)
        self.vote_granted = vote_granted
