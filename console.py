import can
import can_remote

def main():
    print('Send')
    with can.Bus(interface='remote', channel='ws://localhost:54701', bitrate=50000, receive_own_messages=True) as bus:
        while True:
            str = input()
            id, hex_str = str.split("#")
            
            #data = list()
            #data = list(map(lambda x:int(x), bytes))
            #print(data)
            #data = bytearray.fromhex(hex_str)
            data = list(map(lambda x:int(x, 16), hex_str.split()))
            print(data)
            msg = can.Message(arbitration_id=int(id, 16), data=data)
            bus.send(msg)



if __name__ == "__main__":
   main()
