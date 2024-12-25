import subprocess
from pymongo import MongoClient
import pymongo 
from multiprocessing import Process
import time
import os

# Функція для інкрементації лічильника
def increment_likes(write_concern_uri):
    local_client = MongoClient(write_concern_uri)
    db = local_client.test
    for _ in range(10000):
        success = False
        while not success:
            try:
                db.likes.find_one_and_update({}, {"$inc": {"counter": 1}})
                success = True  # Успішно виконано
            except pymongo.errors.AutoReconnect:
                print("Втрачено з'єднання. Повторна спроба...")
                time.sleep(0.5)  # Чекаємо перед повторною спробою
            except pymongo.errors.WriteConcernError as e:
                print(f"Помилка writeConcern: {e}. Повтор спроби...")
                time.sleep(0.5)  # Чекаємо перед повторною спробою
    
    local_client.close()

# Функція для отримання поточного Primary
def get_primary():
    client = MongoClient("mongodb://localhost:27017")
    rs_status = client.admin.command("replSetGetStatus")
    for member in rs_status["members"]:
        if member["stateStr"] == "PRIMARY":
            return member["name"].split(":")[1]  # Повертаємо порт Primary
    return None

# Функція для запуску ноди
def start_node(port, dbpath, logpath):
    while True:
        res = os.system(
            f"mongod --replSet rs0 --port {port} --dbpath {dbpath} --bind_ip localhost --fork --logpath {logpath} > /dev/null"
        )
        if not res:
            break
        time.sleep(.3)
    print(f"Нода на порту {port} знову запущена.")
    

def stop_node(port):
    try:
        # Отримуємо список процесів, що працюють з портом, і фільтруємо LISTEN
        output = subprocess.check_output(
            f"lsof -i:{port} | grep LISTEN", shell=True
        ).decode("utf-8").strip()
        
        # Розбиваємо по пробілу і беремо PID (перший стовпець)
        pid = output.split()[1]
        
        # Завершуємо процес
        os.system(f"kill -9 {pid}")
        print(f"Нода на порту {port} вимкнена (PID: {pid}).")
    except subprocess.CalledProcessError:
        print(f"Не вдалося знайти процес для порту {port}, або процес вже вимкнений.")

def get_processes_list(w:str="majority") -> list:
    base_uri = "mongodb://localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0"
    processes = []
    for _ in range(10):
        uri_with_wc = base_uri + f"&w={w}&wtimeoutMS=5000"
        p = Process(target=increment_likes, args=(uri_with_wc,))
        processes.append(p)
        p.start()
        
    return processes

def test(db, type:int=0, disable:bool=False):
    print(f"Тест з writeConcern={type if type else 'majority'} ({'з відключенням Primary'if disable else 'без відключень'})")
    time_start = time.time()
    processes = get_processes_list(type)

    if disable:
        # Чекаємо 2 секунди та відключаємо поточний Primary
        time.sleep(2)
        current_primary_port = get_primary()
        print(f"Вимикаємо Primary на порту {current_primary_port}...")
        
        stop_node(current_primary_port)

    for p in processes:
        p.join()  # Чекаємо завершення всіх процесів
    if not type:
        for i in range(4):
            if int(db.likes.find_one()['counter']) == 100_000:
                break 
            time.sleep(1)
    print(f"Фінальний лічильник (writeConcern=1): {db.likes.find_one()['counter']}")
    print(f"Time: {time.time()-time_start} s.\n\n")
    if disable:
        input(f"Очікуємо поки буде увімкнено вимкнену ноду на порту {current_primary_port}...")
        print("Користувач увімкнув ноду!\n\n")
    drop_counter(db)


def init_db():
    # Базовий URI для підключення до Replica Set
    base_uri = "mongodb://localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0"

    # Створення колекції
    client = MongoClient(base_uri)
    db = client.test
    db.likes.drop()  # Видаляємо колекцію, якщо вона існує
    db.likes.insert_one({"counter": 0})  # Ініціалізація лічильника
    print("Колекція створена. Поточний лічильник: 0")
    return db

def drop_counter(db):
    db.likes.drop()  # Видаляємо колекцію, якщо вона існує
    db.likes.insert_one({"counter": 0})  # Ініціалізація лічильника
    print("Лічильник оновлено!")

# Основний блок
if __name__ == "__main__":
    # start_node(27017, "../mongodb/rs1", "../mongodb/rs1/mongod.log")
    # start_node(27018, "../mongodb/rs2", "../mongodb/rs2/mongod.log")
    # start_node(27019, "../mongodb/rs3", "../mongodb/rs3/mongod.log")
    db = init_db()
    
    # Тест з writeConcern=1 (без відключень)
    test(db, 1, False)
    test(db, 0, False)
    test(db, 1, True)
    test(db, 0, True)