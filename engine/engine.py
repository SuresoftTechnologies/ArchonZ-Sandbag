
"""
This example shows how sending a single message works.
"""

from typing import Any
from can import Message, Bus, Listener, Notifier, CanError
import random
import time
from abc import abstractmethod
import threading
import asyncio

class Task(Listener):
    _bus: Bus
    
    @abstractmethod
    def get_data(self):
        return None, None

    @abstractmethod
    def run(self, bus:Bus):
        pass

    @abstractmethod
    def is_fd(self):
        return True
    

    def send(self, id, data, is_fd = True):
        msg = Message(arbitration_id=id, data=data, is_extended_id=is_fd)
        try:
            self._bus.send(msg)
        except CanError:
            print("Message NOT sent")


    def _set_bus(self, bus: Bus):
        self._bus = bus
        pass

    def _send(self):
        try:
            self.run(self._bus)
        except:
            pass
        
        id, data = self.get_data()
        if id is None or data is None:
            # nothing to declare
            return
        #print(data)
        msg = Message(
            arbitration_id=id, data=data, is_extended_id=self.is_fd()
            )
        try:
            self._bus.send(msg)
        except CanError:
            print("Message NOT sent")


class PeriodicSleeper(threading.Thread):
    def __init__(self, task_function, period):
        super().__init__()
        self.task_function = task_function
        self.period = period
        self.i = 0
        self.t0 = time.time()

    def sleep(self):
        self.i += 1
        delta = self.t0 + self.period * self.i - time.time()
        if delta > 0:
            time.sleep(delta)
    
    def run(self):
        while True:
            self.task_function()
            self.sleep()


class Engine:
    def __init__(self, bus:Bus) -> None:
        if bus is not None:
            self.bus = bus
        else:
            self.bus = Bus(interface='remote', channel='ws://localhost:54701', bitrate=50000, receive_own_messages=True)
        self.tasks = []
        self.listeners = []
        pass
    
    def register_task(self, task: Task, recv_ids: list, period:float):
        task._set_bus(self.bus)
        self.tasks.append(PeriodicSleeper(task._send, period))
        self.listeners.append(task)
        pass

    def start(self):
        for t in self.tasks:
            t.start()

        print("Initlaize Listeners")
        Notifier(self.bus, self.listeners, timeout=10)
        
        while(True):
            time.sleep(1)

    def stop():
        pass