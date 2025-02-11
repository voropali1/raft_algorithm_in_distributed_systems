#  Base class for messages with shared attributes, like sender ID and timestamp.
import json


class BaseMessage:
    def __init__(self, term, sender_id):
        self.term = term
        self.sender_id = sender_id

    def to_json(self):
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        return cls(**data)

    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
