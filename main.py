import hashlib
import json
from time import time
from typing import Any,Dict,List,Optional
from urllib.parse import urlparse
from uuid import uuid4
import requests
from flask import Flask,jsonify,request

class Blockchain:
    def __init__(self):
        self.current_transactions = []
        self.chain = []
        self.nodes = set()

        #创建创世块
        self.new_block(previous_hash='1',proof=100)

    def register_node(self,address:str)->None:
        """
        注册新的节点
        :param address:新节点的访问地址
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain:List[Dict[str,Any]])->bool:
        """
        判断区块链的有效性
        :param chain:待判断区块链
        :return:有效就返回True，无效返回False
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            if block['previsous_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

        return True

    def resolve_conflicts(self) -> bool:
        """
        共识算法解决冲突：使用网络中最长的链

        :return: 如果链被取代返回 True, 否则返回 False
        """

        neighbours = self.nodes
        new_chain = None

        #寻找长度比当前链条更长的区块链，替换当前链
        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                #长度更大，且有效
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

                if new_chain:
                    self.chain = new_chain
                    return True

                return False

    def new_block(self, proof: int, previous_hash: Optional[str]) -> Dict[str, Any]:
        """
        生成新的区块并返回
        :param proof: 工作量证明
        :return: 新创建的区块
        """

        block = {
            "index":len(self.chain)+1,
            "timestamp":time(),
            "transactions": self.current_transactions,
            "proof": proof,
            "previous_hash": previous_hash or self.hash(self.chain[-1]),
        }

        self.current_transactions = []
        self.chain.append(block)

        return block

    def new_transaction(self, sender: str, recipient: str, amount: int) -> int:
        """
        生成新的交易信息
        :param sender: sender的地址
        :param recipient: receiver的地址
        :return: 添加新交易的区块所处的索引号
        """

        self.current_transactions.append({
            "sender": sender,
            "recipient": recipient,
            "amount": amount
        })

        return self.last_block['index'] + 1

    @property
    def last_block(self) -> Dict[str, Any]:
        return self.chain[-1]

    @staticmethod
    def hash(block: Dict[str, Any]) -> str:
        """
        生成块的 SHA-256 hash值
        :param block: 待计算的区块
        """

        block_string = json.dumps(block, sort_keys=True).encode()

        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_proof: int) -> int:
        """
        工作量证明
        前面工作量值是X，查找一个数字Y满足 hash(XY) 前面是4个0
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    def valid_proof(self, last_proof: int, proof: int) -> bool:
        """
        验证工作量是有效
        :param last_proof:前面的工作量
        :param proof:当前的工作量
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        return guess_hash[:4] == '0000'

# 下面是处理网络请求的部分
app = Flask(__name__)
node_id = str(uuid4()).replace('-','')
blockchain = Blockchain()

@app.route('/mine',methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transaction('0',node_id,1)
    block = blockchain.new_block(proof, None)

    response = {
        "message": "New Block",
        "index": block['index'],
        "transactions": block["transactions"],
        "proof": block["proof"],
        "previous_hash": block["previous_hash"],
    }

    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    #检查POST数据
    required = ['sender','recipient','amount']
    if not all(k in values for k in required):
        return 'following fields not all existed: sender, recipient, amount'

    index = blockchain.new_transaction(values['sender'],values['recipient'],values['amount'])
    response = {
        "message", f'new transaction will be added: ${index}'
    }

    return jsonify(response), 201
    
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        "chain": blockchain.chain,
        "length": len(blockchain.chain)
    }

    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')

    if nodes is None:
        return 'Invalid request', 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        "message": "new nodes have been added",
        "total_nodes": list(blockchain.nodes)
    }

    return jsonify(response), 201

@app.route('/nodes/resolve', methods = ['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    message = ''

    if replaced:
        message = 'node has been replaced.'
    else:
        message = 'node are fresh'

    response = {
        "message": message,
        "new_chain": blockchain.chain
    }

    return jsonify(response), 200

if __name__ == 'main':
    from argparse import ArgumentParser
    
    parser = ArgumentParser()
    parser.add_argument('-p','--port',default=5000,type=int, help='port on listening...')
    args = parser.parse_args()
    port = args.port

    app.run(host='127.0.0.1',port=port)