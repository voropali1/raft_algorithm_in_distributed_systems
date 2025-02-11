# Raft Consensus Algorithm in Python

This project implements the Raft Consensus Protocol in Python. The Raft algorithm is a consensus algorithm designed for managing a replicated log, commonly used in distributed systems. This README will guide you through the folder structure, the Docker setup for simulating nodes, and how to run the application.

## Project Structure

Here's a breakdown of the project folder structure:

```plaintext
raft-consensus-python/
├── client/
│   ├── static/                  # Static files for the client side.
│   ├── templates/
│   │   └── index.html           # HTML template for client UI
│   └── client.py                # Client code interacting with nodes(The leader node in this case)
├── disk/
│   └── leader_logs.db           # Persistent log storage
├── messages/
│   ├── __init__.py
│   ├── base_message.py          # Base class for messages between nodes
│   ├── heartbeat.py             # Heartbeat messages for leader health check
│   ├── vote_request.py          # Messages for requesting votes in an election
│   └── vote_response.py         # Response messages for vote requests
├── servers/
│   ├── candidate.py             # Logic for candidate node state
│   ├── follower.py              # Logic for follower node state
│   └── leader.py                # Logic for leader node state
│   └── node.py                  # Logic for shared node functinalities
├── tests/
│   ├── test_message_sending.py  # Some basic tests for testing inter-node communication
├── .gitignore                   # Git ignore file
├── Dockerfile                   # Dockerfile to build the application image
├── docker-compose.yml           # Docker Compose file to spin up nodes
├── main.py                      # Entry point for running the Raft protocol
├── README.md                    # Project documentation (this file)
└── requirements.txt             # Dependencies
```

## Setting Up the Project

**Create a Python Virtual Environment**

To manage dependencies locally can create a Python virtual environment. Run the following command:

```bash
python3 -m venv venv
```

**Activate the Virtual Environment**
- On macOS/Linux:
```bash
source venv/bin/activate
```
- On windows:
```bash
venv\Scripts\activate
```

## Running the Project

To simulate a Raft cluster, we use Docker and Docker Compose. The `docker-compose.yml` file defines three nodes, each running as an independent service and communicating over a bridge network.

### Docker Compose Configuration

The `docker-compose.yml` file defines three services:

- **node1**, **node2**, and **node3**: Each node has its own ID and communicates with its peers to simulate a cluster network. The environment variables define the node ID and the list of peers each node can communicate with.
- **Ports**: Each node exposes port `5000` internally, mapped to an external port (`6500`, `6501`, `6502` for each node respectively) for inter-node communication.
- **Volumes**: Each node mounts the `disk` directory to persist log data across container restarts.

### Build and Start the Cluster

Use the following command to build the Docker images and start the cluster:

```bash
docker-compose up --build
```

### Stopping the cluster 
```bash
docker-compose down
```
### Starting the Client
Navigate to the Client project directory:
```bash
cd raft-consensus-python
cd client
```
To run the client program run:
```bash
python client.py
```


### Testing the Program.
At this point you program should be running. Observe the logs and you should see an election has occured and the leader is sending hearbeats.
To test the program do the following:
1. Send a message from the client side. Observe the logs and you will see the message has been replicated and check the `leader_logs.db` inside the disk folder to see that you message has been committed. 
2. On the client side UI kill the leader node. Observe the logs, you will notice a re-election and a new leader sending hearbeats. 
3. To restart the previous leader node open a new terminal and run the following command:
```bash
docker-compose up node[id] 
```
for example if node1 was the leader or the node you killed you would run: 
```bash
docker-compose up node1 
```

You will notice that the node transitions into a follower state and starts receiving heartbeats from the current leader. 

### Key Features of Raft Consensus Protocol Implementation

1. **Cluster Simulation with Docker**: 
   Docker containers simulate a cluster of nodes, establishing internal networking for node communication.

2. **Node Initialization & Election**:

3. **Leader-Follower Architecture**:
   - Leader node sends heartbeats to followers, maintaining synchronization and preventing split votes.
   - Follower nodes reset election timeouts on receiving heartbeats.

4. **Client and Cluster Interaction**:
   - Client requests directed to the leader, which updates followers upon log commit.
   - Transparent leader re-assignment if leader node changes.
   - Dynamic re-routing of client requests maintains consistent user experience.

5. **Log Reconciliation**:
   - **Term Validation**: Followers accept leader updates only if the term is current.
   - **Log Integrity Checks**: Followers verify logs with the leader to identify inconsistencies.
   - **Conflict Resolution**: Conflicting log entries are removed and replaced with leader’s entries.
   - **Commit Index Synchronization**: Followers align commit indexes with the leader to confirm identical logs.

6. **Fault Tolerance**:
   - Handles leader failures with automatic re-elections.
   - Client operations uninterrupted through leader reassignment and transparent redirection.



## Protocol Analysis and Documentation

As mentinoed before, this Raft consensus protocol implementation uses Docker to simulate a cluster and establish an internal network between nodes. When you run the command `docker-compose up --build`, three server instances will spin up. You might notice a slight delay before the log nodes start; this is entirely intentional. In our `node.py` file, within the `start_node` method, we have a `time.sleep` of one second. This ensures all node servers initialize correctly before beginning interactions between them.

### Node Initialization and Election Process

Once all nodes are initialized, they transition to the `follower_state`. At this point, the nodes wait for their respective election timeouts to initiate an election. When an election concludes, the winning node transitions to the `leader_state` and immediately begins sending heartbeat signals to the follower nodes.

In the event of a split vote, all nodes will return to the `follower_state`, and the election timeouts will restart to initiate a new election. Although there are more robust methods to handle split votes, we opted for this approach for simplicity and clarity.


### Leader-Follower (Master-Slave) Architecture

After a node enters the `leader_state`, it begins sending heartbeat messages to all follower nodes. Each heartbeat resets the follower nodes' election timeouts, preventing unnecessary elections. These heartbeat messages carry empty entries and help maintain synchronization between nodes.

With each heartbeat, the follower nodes verify the `term` value to ensure it aligns with the leader’s term. They also check for consistency in the `previous_log_index` and `previous_log_term`. We will cover the process for reconciling stale logs later in this document.

Referencing our Leader-Follower Architecture, the protocol also includes a client that can send messages to the cluster. In the client UI, once you input a message into the form, the request is sent to the leader node. The leader node appends this message to its logs and propagates it to the replica nodes. When the leader receives acknowledgments from a majority of replicas, it commits the message to `leader_logs.db`, introducing persistence and supporting consistency when bringing new nodes up to speed. The database integration enables us to simulate a true commit upon receiving majority acknowledgments from replica nodes.


#### Client & CLuster Interaction 
If you kill and restart our cluster multiple times, you’ll notice that a new leader node is elected each time. To handle leader changes seamlessly, we’ve introduced some functionality that dynamically re-assigns the leader. 

In our cluster, if the client sends a request to a node that is no longer the leader, we redirect the client requests to the leader node within the cluster and send back the new address to the client for future requests. This allows the client to continue operating as if interacting with a single, stable endpoint, regardless of changes in the leader node . 

This approach follows the **principle of transparency in distributed systems**, where the client interacts with the cluster as though it’s a single machine, without being aware of underlying changes like leader re-elections.

#### Demonstrating Transparency in Leader Re-assignment

To see this transparency in action:
1. **Kill the Leader Node** from the Client UI.
2. **Send a Message** from the client.

You’ll observe that the message is successfully processed, even though the leader has changed. The cluster and client handles the re-routing seamlessly, maintaining consistent communication with the current leader without requiring user intervention.</br>
This method ensures that changes in the leader node remain transparent to the client, supporting a smooth and uninterrupted user experience.</br>
Finally, on the client side a user is able to kill any particular node in the cluster. For example, if you were to kill the leader node you will notice in the logs that a new re-election will occur and new leader will automatically start sending hearbeats.

### Log Reconciliation in Raft Protocol

In Raft, log reconciliation ensures consistency across nodes by maintaining identical logs on the leader and follower nodes. When a leader sends heartbeat messages, it includes its log state to help followers keep up-to-date. Here’s how the reconciliation process works in our implementation:

1. **Term Validation**: 
   When a follower receives an `append_entries` request (heartbeat), it checks if the leader’s term is current. If the term is outdated, the request is rejected to maintain consistency. If the leader’s term is higher, the follower updates its term and accepts the leader as the valid authority.

2. **Log Integrity Checks**:  
   The follower verifies that its log matches the leader’s at a specific point, using `prev_log_index` and `prev_log_term`. If the follower’s log is shorter or has mismatched terms at that index, the request is rejected, signaling an inconsistency. This triggers the leader node to send new entries to the follower node to ammend the inconsistency. This is discussed below.  

3. **Appending New Entries**:
   When consistency is confirmed, any new entries are appended. If there’s a conflict (mismatched entries at the same index), conflicting entries are removed from the follower’s log, and the new entries from the leader are appended.

4. **Commit Index Update**:
   The follower updates its `commit_index` to match the leader’s committed entries, up to the point where both logs are aligned. This ensures that only confirmed entries are marked as committed, maintaining consistency across nodes.

This approach guarantees that each follower has an identical log to the leader, resolving any inconsistencies as entries are appended. The follower’s log is thus consistently reconciled to reflect the leader’s log, ensuring a uniform state across the cluster.


### Protocol Shortcomings
- **Node Resilience**: Once a node goes down, it does not automatically restart. Despite configuring Docker for automatic restarts, seamless respawning remains an issue. Enabling this feature would be a valuable enhancement, allowing us to observe real-time log reconciliation when nodes reconnect.

- **Log Replication and Truncation**: During log inconsistencies, our current approach truncates follower logs to match the leader, which can result in data loss if a network partition occurs and splits the cluster. This could lead to missing entries on some followers when they rejoin the cluster.

- **Follower Commit Limitations**: Only the leader node commits log entries to a database, serving as our single source of truth. Follower nodes lack databases, so they do not persist their logs independently, relying solely on the leader's state.

- **Single Database Bottleneck**: Our architecture uses a single database (`leader_logs.db`) on the leader node. This design could become a bottleneck and create inconsistencies during a network partition. If the cluster splits, database commits could be affected, as they rely on one centralized source. Additionally, since we would now have two new leader nodes(in the case of a bigger cluster) we run into the risk of our `leader_logs.db` being corrupt since it has two leaders appending to it at the same time. 


### AI Usage 
AI was instrumental in building much of the foundational code for this project. However, as the codebase grew, its performance declined significantly, particularly in managing the complexities of a multi-threaded program. Handling state consistently was challenging, and ChatGPT struggled with resolving issues related to concurrency and state management.</br>
Additionally, ChatGPT often made assumptions about the Raft algorithm that didn’t align with the actual implementation. I frequently had to guide the model, clarifying the nuances of the consensus algorithm to receive relevant suggestions. While AI was a useful tool for initial development, it quickly became less effective as the code grew in complexity and required more nuanced understanding.





