from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
from requests.exceptions import ConnectionError, RequestException

app = Flask(__name__)

# List of node addresses
nodes = [
    {"id": "1", "address": "http://localhost:6500"},
    {"id": "2", "address": "http://localhost:6501"},
    {"id": "3", "address": "http://localhost:6502"},
]

leader_address = None  # Global variable to store the current leader address


def find_leader():
    """
    Queries each node to determine the current leader.
    Returns the leader's address if found, else None.
    """
    global leader_address
    for node in nodes:
        try:
            response = requests.get(f"{node['address']}/state", timeout=2)
            if response.status_code == 200:
                data = response.json()
                if data["state"] == "Leader":
                    leader_address = node["address"]
                    return leader_address
        except ConnectionError:
            continue  # Node is unreachable, try the next one
        except requests.exceptions.RequestException:
            continue  # General request exception, try the next one
    leader_address = None
    return None


@app.route("/", methods=["GET", "POST"])
def index():
    global leader_address
    if request.method == "POST":
        message = request.form.get("message")

        # Ensure we have the current leader's address
        if leader_address is None:
            leader_address = find_leader()

        # If no leader is found after the check, return an error
        if not leader_address:
            return render_template(
                "index.html", error="No leader available to handle the request."
            )

        # Attempt to send the message to the leader
        try:
            response = requests.post(
                f"{leader_address}/client_request",
                json={"message": message},
                timeout=2,
            )
            if response.status_code == 200:
                return render_template("index.html", success=True)
            elif response.status_code == 400:
                # If the response indicates a different leader, update and retry
                data = response.json()
                if "leader" in data:
                    leader_address = data["leader"]
                    response = requests.post(
                        f"{leader_address}/client_request",
                        json={"message": message},
                        timeout=2,
                    )
                    if response.status_code == 200:
                        return render_template("index.html", success=True)
        except requests.exceptions.RequestException:
            # If the leader didn't respond, try to find a new leader and resend
            leader_address = find_leader()
            if leader_address:
                try:
                    response = requests.post(
                        f"{leader_address}/client_request",
                        json={"message": message},
                        timeout=2,
                    )
                    if response.status_code == 200:
                        return render_template("index.html", success=True)
                except requests.exceptions.RequestException:
                    pass  # Leader still unresponsive

        # If we can't reach a leader, return an error
        return render_template(
            "index.html", error="Could not send message to any leader."
        )
    return render_template("index.html")


@app.route("/kill_node/<node_id>", methods=["POST"])
def kill_node(node_id):
    node = next((node for node in nodes if node["id"] == node_id), None)
    if node:
        try:
            duration = 30  # Set default duration to 30 seconds
            response = requests.post(
                f"{node['address']}/shutdown", json={"duration": duration}, timeout=2
            )
            if response.status_code == 200:
                return render_template(
                    "index.html",
                    success=True,
                    message=f"Node {node_id} shutdown initiated for {duration} seconds",
                )
        except ConnectionError:
            return render_template(
                "index.html",
                error=f"Node {node_id} is already unreachable or shut down.",
            )
        except RequestException as e:
            return render_template(
                "index.html", error=f"Failed to shutdown node {node_id}: {str(e)}"
            )
    return render_template("index.html", error=f"Node {node_id} not found")


if __name__ == "__main__":
    app.run(debug=True)
