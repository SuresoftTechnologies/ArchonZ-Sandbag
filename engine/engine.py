
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
    _name: str
    
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
        except Exception as e:
            print(e)
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
    def __init__(self, task_name, task_function, period):
        super().__init__()
        self.task_function = task_function
        self.period = period
        self.i = 0
        self.t0 = time.time()
        self.name = task_name
        self._stop_event = threading.Event()  # 스레드 중지 이벤트 추가
        self.daemon = True  # 메인 스레드 종료 시 같이 종료되도록 설정

    def sleep(self):
        self.i += 1
        delta = self.t0 + self.period * self.i - time.time()
        if delta > 0:
            time.sleep(delta)
    
    def run(self):
        while not self._stop_event.is_set():  # 중지 이벤트 확인
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
        self.stopped_tasks = []  # 중지된 태스크 추적
        pass
    
    def register_task(self, task: Task, recv_ids: list, period:float):
        task._set_bus(self.bus)
        self.tasks.append(PeriodicSleeper(task._name, task._send, period))
        self.listeners.append(task)
        pass

    def start(self):
        notifier = None
        try:
            for t in self.tasks:
                t.start()

            print("Initlaize Listeners")
            notifier = Notifier(self.bus, self.listeners, timeout=10)
            
            while(True):
                try:
                    time.sleep(1)
                except KeyboardInterrupt:
                    print("Keyboard interrupt received, stopping...")
                    break
                
        except Exception as e:
            print(f"Error stopping notifier: {e}")
        finally:
            self.stop_all_task()

            if notifier:
                try:
                    notifier.stop()
                    print("Notifier stopped")
                except Exception as e:
                    print(f"Error stopping notifier: {e}")

            print("Notifier stopped")
        try:
            self.bus.shutdown()
            print("Bus shut down")
        except (BrokenPipeError, ConnectionError):
            print("Bus connection was already closed")
        except Exception as e:
            print(f"Error shutting down bus: {e}")
            

    def stop_all_task(self):
        """모든 태스크를 안전하게 중지합니다."""
        print("Stopping all tasks...")
        self.stopped_tasks = []

        for t in self.tasks:
            if hasattr(t, '_stop_event') and t._stop_event.is_set():
                continue
            try:
                t._stop_event.set()  # 종료 이벤트 설정
                self.stopped_tasks.append(t)  # 중지된 태스크 추적
                print(f"{t.name} task is stopped")
            except AttributeError:
                print(f"Cannot stop {t.name}: missing _stop_event attribute")
            except Exception as e:
                print(f"Error stopping {t.name}: {e}")

    def resume_all_tasks(self):
        print("Resuming stopped tasks...")
        resumed_count = 0
        
        for t in self.stopped_tasks:
            try:
                if hasattr(t, '_stop_event'):
                    # 중지 이벤트 해제
                    t._stop_event.clear()
                    # 스레드가 이미 종료되었다면 재시작
                    if not t.is_alive():
                        # 새 스레드 생성 및 시작
                        new_thread = PeriodicSleeper(t.name, t.task_function, t.period)
                        # 기존 태스크 리스트에서 중지된 스레드 교체
                        idx = self.tasks.index(t)
                        self.tasks[idx] = new_thread
                        new_thread.start()
                    
                    print(f"{t.name} task is resumed")
                    resumed_count += 1
            except Exception as e:
                print(f"Error resuming {t.name}: {e}")
        
        # 재개된 태스크 목록에서 제거
        self.stopped_tasks = []
        
        print(f"Resumed {resumed_count} tasks")

    def stop():
        pass