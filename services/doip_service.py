#from doip_lib.discover import DOIPDiscoverThread
from doip_lib.server import DOIPServer

from doip_lib import utils
from doip_lib.simulator import framp, fsine, IdentifierDataSimulator

def accelerator_format(n):
    return [n]

def brakehydralic_format(n):
    return utils.num_to_bytes(n, 2)

def steeringangle_format(n):
    sign = 1 if n < 0 else 0
    magnitude = abs(n)
    return utils.num_to_bytes(magnitude, 2) + [sign]


config = {
    'vin': 'TESTVIN0000012345',
    'mac': int('123456789ABC', 16),
    'addresses': {
        'discovery': 0x3000,
        'server': 0x3010,
    },
    'datamap': {
        0x3300: {
            0x3200: ('Dummy Accelerator', framp(0xff, 2, 0), accelerator_format),
            0x3230: ('Dummy Brake', framp(0x5000, 10, 0), brakehydralic_format),
        },
        0x3301: {
            0x3250: ('Dummy Steering', fsine(0x7fff, 4, 0), steeringangle_format),
        }
    }
}

def run_doip():
    simulator = IdentifierDataSimulator(config['datamap'])

    # ijwoo - discover thread를 돌리면 doipclient 쪽에서 응답 timeout 에 걸려 에러가 발생하므로 주석 처리함
    # discovery_thread = DOIPDiscoverThread(config)
    # discovery_thread.start()

    server = DOIPServer(config, simulator)
    server.serve_forever()

if __name__ == '__main__':
    run_doip()