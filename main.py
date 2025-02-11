import argparse
from servers.node import Node
import logging
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,  # Устанавливаем уровень логирования
    format="[%(asctime)s] %(levelname)s - %(message)s",
)

def parse_args():
    parser = argparse.ArgumentParser(description="Run a Node for Raft Consensus")
    parser.add_argument('--hostname', type=str, required=True, help='Hostname for the node')
    parser.add_argument('--port', type=int, required=True, help='Port for the node to run on')
    parser.add_argument('--node_id', type=int, required=True, help='Unique Node ID')
    parser.add_argument('--is_first', action='store_true', default=False, help='Indicate if this is the first node in the cluster')
    
    return parser.parse_args()

def main():
    # Парсим аргументы командной строки
    args = parse_args()
    
    # Получаем hostname и port из аргументов
    hostname = args.hostname
    port = args.port
    node_id = args.node_id
    is_first = args.is_first
    
    # Создание экземпляра Node
    node = Node(node_id=args.node_id, hostname=args.hostname, port=args.port, is_first=is_first)

    # Запуск узла
    logging.info(f"Starting Node {node_id} on {hostname}:{port}")
    Node.get_all_nodes().append(node)
    
    logging.info(f"Node {node_id} is running on {hostname}:{port}.")
    
    # Можно добавить дополнительные шаги, например, мониторинг или переключение состояний
     # Периодическая проверка или дополнительная логика

if __name__ == "__main__":
    main()
    
    #python main.py --hostname 127.0.0.1 --port 2000 --node_id 1 --is_first
    #python main.py --hostname 127.0.0.1 --port 2001 --node_id 2
    #python main.py --hostname 127.0.0.1 --port 2002 --node_id 3
    #python main.py --hostname 127.0.0.1 --port 2003 --node_id 4

