import unittest
import requests
import time


class TestMessageSending(unittest.TestCase):

    def setUp(self):
        
        # Define the base URLs for each node, using the host-exposed ports
        self.nodes = {
            "node1": "http://localhost:6500",
            "node2": "http://localhost:6501",
            "node3": "http://localhost:6502",
        }
        # Message payload to send
        self.message_payload = {"message": "Test message from test case"}

    def test_send_message_from_node1(self):
        """
        Test sending a message from Node 1 to Node 2 and Node 3.
        """
        response = requests.post(
            f"{self.nodes['node1']}/send_message", json=self.message_payload
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Message sent to peers", response.json()["status"])

        # Wait for a short period to allow message delivery
        time.sleep(1)

        # Verify that Node 2 and Node 3 received the message
        for node_name, url in [
            ("node2", self.nodes["node2"]),
            ("node3", self.nodes["node3"]),
        ]:
            response = requests.get(f"{url}/message_log")
            self.assertEqual(response.status_code, 200)
            messages = response.json().get("messages", [])
            print(messages)
            self.assertTrue(
                any(self.message_payload["message"] in msg[1] for msg in messages),
                f"{node_name} did not receive the message from Node 1",
            )

    def test_send_message_from_node2(self):
        """
        Test sending a message from Node 2 to Node 1 and Node 3.
        """
        response = requests.post(
            f"{self.nodes['node2']}/send_message", json=self.message_payload
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Message sent to peers", response.json()["status"])

        # Wait for a short period to allow message delivery
        time.sleep(1)

        # Verify that Node 1 and Node 3 received the message
        for node_name, url in [
            ("node1", self.nodes["node1"]),
            ("node3", self.nodes["node3"]),
        ]:
            response = requests.get(f"{url}/message_log")
            self.assertEqual(response.status_code, 200)
            messages = response.json().get("messages", [])
            self.assertTrue(
                any(self.message_payload["message"] in msg[1] for msg in messages),
                f"{node_name} did not receive the message from Node 2",
            )
            
if __name__ == "__main__":
    unittest.main()
