import hazelcast
import threading
import time
from datetime import datetime

class HCClient:
    def __init__(self, type:int, count:int=10000, thread_num:int=10, is_atomic:bool = False) -> None:
        self.client = hazelcast.HazelcastClient(
            cluster_members=[
                "127.0.0.1:5701",
                "127.0.0.1:5702",
                "127.0.0.1:5703"
            ]
        )
        self.threads = []
        self.thread_num = thread_num
        self.count = count
        self.is_atomic = is_atomic
        self.map = "counter_map"
        self.key = "counter_key"
        self.distributed_map = self.client.get_map(self.map).blocking() if not self.is_atomic else self.client.cp_subsystem.get_atomic_long(self.key).blocking()
        self.func_names = [
            "increment",
            "optimistic",
            "pessimistic",
            "atomic"
        ]
        self.type = type


    def get_value(self) -> int:
        if self.is_atomic:
            val = self.distributed_map.get()
        else:
            try:
                val = self.distributed_map.get(self.key)
                if not val:
                    val = 0
            except:
                val = 0
        return val
    
    def set_zero(self) -> bool:
        try:
            if self.is_atomic:
                self.distributed_map.set(0)
            else:
                self.distributed_map.put(self.key, 0)
            return True
        except:
            return False
    



    def increment_counter(self):
        for _ in range(self.count):
            counter = self.distributed_map.get(self.key) or 0
            self.distributed_map.put(self.key, counter + 1)

    def optimistic_increment(self):
        for _ in range(self.count):
            while True:
                old_value = self.distributed_map.get(self.key)
                new_value = (old_value or 0) + 1

                if self.distributed_map.replace_if_same(self.key, old_value, new_value):
                    break

    def pessimistic_increment(self):
        for _ in range(self.count):
            self.distributed_map.lock(self.key)
            try:
                counter = self.distributed_map.get(self.key) or 0
                self.distributed_map.put(self.key, counter + 1)
            finally:
                self.distributed_map.unlock(self.key)
    
    def atomic_increment(self):
        for _ in range(self.count):
            self.distributed_map.increment_and_get()





    
    def monitoring(self, timer:int=5):
        while any(thread.is_alive() for thread in self.threads):
            self.get_log()
            time.sleep(timer)

    def get_log(self):
        current_count = self.get_value()
        cur_date = datetime.now().strftime("%H:%M:%S %d.%m")
        print(f"{cur_date} -- counter: {current_count}")
    
    def test_func(self):
        self.set_zero()
        print('setted 0')
        self.get_log()
        funcs = [
            self.increment_counter,
            self.optimistic_increment,
            self.pessimistic_increment,
            self.atomic_increment
        ]
        if self.type > len(funcs):
            return False
        print(f"Starting: {self.func_names[self.type]}")
        start_time = time.time()
        for _ in range(self.thread_num):
            thread = threading.Thread(target=funcs[self.type])
            thread.start()
            self.threads.append(thread)
        
        self.monitoring(10)
        # monitor = threading.Thread(target=self.monitoring)
        # monitor.start()
        # time.sleep(10)
        # self.get_log()
        # for thread in self.threads:
        #     thread.join()

        txt = [
            f"\n\nResult for {self.func_names[self.type]}",
            f"Counter value: {self.get_value()}",
            f"Time: {round(time.time()-start_time,2)}s",
            "————————————————————————————————————————————————"
        ]

        print("\n".join(txt))

    def main(self):
        for i in range(self.func_names):
            
            if not self.test_func(i):
                print("pizdec")
        
if __name__ == "__main__":
    for i in range(4):
        atom = i == 3
        print(f'initing type: {i}, atomic -- {atom}')
        hc = HCClient(type=i, is_atomic=atom)
        print('inited')
        hc.test_func()
        hc.client.shutdown()
    