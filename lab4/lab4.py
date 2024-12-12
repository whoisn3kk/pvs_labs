from pymongo import MongoClient

uri = "mongodb://172.21.0.3:27017,172.21.0.4:27017,172.21.0.5:27017/?replicaSet=rs0"
client = MongoClient(uri)

# Проверка подключения
db = client.testc
print(db.command("ping"))
