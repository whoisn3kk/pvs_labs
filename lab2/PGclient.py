from datetime import datetime
from functools import wraps
import threading
import time
from traceback import format_exc
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()
DBNAME = os.environ.get("DBNAME")
DB_USER = os.environ.get("DB_USER")
PASSWORD = os.environ.get("PASSWORD")
HOST = os.environ.get("HOST")

def db_connection_decorator(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**self.config)
            cursor = conn.cursor()
            result = func(self, cursor, conn, *args, **kwargs)
            conn.commit()
            return result
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Database error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    return wrapper


class PGClient:
    def __init__(self, type:int, DBNAME:str, DB_USER:str, PASSWORD:str, HOST:str, iterations:int=10000, thread_num:int=10) -> None:
        self.config = {
            "dbname":DBNAME, 
            "user":DB_USER, 
            "password":PASSWORD, 
            "host":HOST
        }
        self.iterations = iterations
        self.type = type
        self.threads = []
        self.thread_num = thread_num
        self.func_names = [
            "Lost-update",
            "In-place update",
            "Row-level locking",
            "Optimistic concurrency control"
        ]
        pass
    
    @db_connection_decorator
    def create_rewrite_user(self, cursor, conn) -> bool:
        try:
            cursor.execute("SELECT counter FROM user_counter WHERE user_id = 1")
            result = cursor.fetchone()
            if result:
                return True 
            cursor.execute("INSERT INTO user_counter (user_id, counter, version) VALUES (1, 0, 0)")
            return True 
        except:
            print(format_exc())
            return False


    @db_connection_decorator
    def get_value(self, cursor, conn) -> int:
        cursor.execute("SELECT counter FROM user_counter WHERE user_id = 1")
        counter = cursor.fetchone()[0]
        return counter

    @db_connection_decorator
    def set_zero(self, cursor, conn) -> bool:
        try:
            cursor.execute("UPDATE user_counter SET counter = 0, version = 0 WHERE USER_ID = 1")
            return True
        except:
            print(format_exc())
            return self.create_rewrite_user()

    ### METHODS ###
    # Lost-update
    @db_connection_decorator
    def lost_update(self, cursor, conn):
        for _ in range(self.iterations):
            cursor.execute("SELECT counter FROM user_counter WHERE user_id = 1")
            counter = cursor.fetchone()[0]
            cursor.execute("UPDATE user_counter SET counter = %s WHERE user_id = 1", (counter + 1,))
            conn.commit()
    
    #In-place update
    @db_connection_decorator
    def in_place_update(self, cursor, conn):
        for _ in range(self.iterations):
            cursor.execute("UPDATE user_counter SET counter = counter + 1 WHERE user_id = 1")
            conn.commit()
    
    #Row-level locking
    @db_connection_decorator
    def row_level_locking(self, cursor, conn):
        for _ in range(self.iterations):
            cursor.execute("SELECT counter FROM user_counter WHERE user_id = 1 FOR UPDATE")
            counter = cursor.fetchone()[0]
            cursor.execute("UPDATE user_counter SET counter = %s WHERE user_id = 1", (counter + 1,))
            conn.commit()

    #Optimistic concurrency control
    @db_connection_decorator
    def optimistic_concurrency_control(self, cursor, conn):
        for _ in range(self.iterations):
            while True:
                cursor.execute("SELECT counter, version FROM user_counter WHERE user_id = 1")
                counter, version = cursor.fetchone()
                cursor.execute("UPDATE user_counter SET counter = %s, version = %s WHERE user_id = 1 AND version = %s", (counter + 1, version + 1, version))
                conn.commit()
                if cursor.rowcount > 0:
                    break

    
    def monitoring(self, timer:int=5):
        while any(thread.is_alive() for thread in self.threads):
            self.get_log()
            time.sleep(timer)

    def get_log(self):
        current_count = self.get_value()
        cur_date = datetime.now().strftime("%H:%M:%S %d.%m")
        print(f"{cur_date} -- counter: {current_count}")
    

    def test_func(self):
        if not self.set_zero():
            print("Failed to set 0")
            return False
        print('setted 0')
        # self.get_log()
        funcs = [
            self.lost_update,
            self.in_place_update,
            self.row_level_locking,
            self.optimistic_concurrency_control
        ]
        if self.type > len(funcs):
            return False
        print(f"Starting: {self.func_names[self.type]}")
        start_time = time.time()
        for _ in range(self.thread_num):
            thread = threading.Thread(target=funcs[self.type])
            thread.start()
            self.threads.append(thread)
        
        self.monitoring()
        monitor = threading.Thread(target=self.monitoring, daemon=True)
        monitor.start()

        for thread in self.threads:
            thread.join()

        txt = [
            f"\n\nResult for {self.func_names[self.type]}",
            f"Counter value: {self.get_value()}",
            f"Time: {round(time.time()-start_time,2)}s",
            "————————————————————————————————————————————————"
        ]

        print("\n".join(txt))

    
if __name__ == "__main__":
    for i in range(4):
        pg = PGClient(i, DBNAME, DB_USER, PASSWORD, HOST)
        pg.test_func()