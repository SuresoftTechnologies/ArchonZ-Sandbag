"""
   Copyright 2019 Rohan Fletcher

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

# Modifier    - ijwoo
# Last change - 2024.03.11

import asyncio
import logging

from . import uds
from . import doip

from . import simulator as sim

logger = logging.getLogger("server")

def my_callback(future):
    result = future.result()
    print("Task completed with result:", result)

class DOIPServer:
    _should_stop_cnt = 0
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DOIPServer, cls).__new__(cls)
        return cls._instance


    def __init__(self, config, simulator):
        if not hasattr(self, 'initialized'):
            self.simulator = simulator
            self.config = config

            self.initialized = True
            self.host = '0.0.0.0'
            self.port = 13400
            self.tcp_server = None
            self.should_restart_tcp = False

            self.should_restart_udp = False
            self.udp_transport = None
            self.udp_protocol = None
            self.loop = None
            
    def serve_forever(self):
        asyncio.run(self.run())

    async def run(self):
        await asyncio.gather(
            self.start_tcp_server(),
            self.start_udp_server(),
        )

        while True:
            await asyncio.sleep(1)
            if self.should_restart_tcp:
                await self.restart_tcp_server()
                self.should_restart_tcp = False
                self._should_stop_cnt = 0


######################
#     tcp server     #
######################
    async def start_tcp_server(self):
        print(f"### start_tcp_server")
        try:
            if not self.tcp_server:
                self.tcp_server = await asyncio.start_server(
                    self.handle_tcp_session, self.host, self.port)
                addr = self.tcp_server.sockets[0].getsockname()
                print(f'DoIP Serving on {addr} by tcp...')

            async with self.tcp_server:
                await self.tcp_server.serve_forever()

            self._should_stop_cnt = 0
            
        # 처음 서버를 재시작한 뒤, 다시 재시작을 하려고 하면 해당 exception이 발생하고 있으나 정확한 이유는 찾지 못함
        except asyncio.CancelledError as e:
            logger.error(f"Unexpected CancelledError error: {e}")
            await asyncio.sleep(5)
            await self.restart_tcp_server()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

     # switch to class to decrease indentation
    async def handle_tcp_session(self, reader, writer):
        client_addr = writer.get_extra_info('peername')
        logger.info('Connection established with %s', client_addr)

        routing_activated = False
        try:
            while True:
                data = await reader.read()
                
                if len(data) == 0:
                    logger.info('Client %s disconnected', client_addr)
                    break

                # 메시지의 전체 길이가 50 이상인 경우, doip 서버가 잠시 종료되고 다시 시작되는 경우를 모사하였음
                elif len(data) >= 50:
                    logger.debug(f"tcp data length : {len(data)}")
                    self._should_stop_cnt += 1
                    logger.debug(f"should_stop_cnt : {self._should_stop_cnt}")

                    if self._should_stop_cnt == 3:
                        self._should_stop_cnt = 0
                        try:
                            self.tcp_server.close()
                            writer.close()
                            await writer.wait_closed()
                            await asyncio.sleep(3)
                            self.should_restart_tcp = True
                            await self.start_tcp_server()
                        except Exception as e:
                            logger.error(f"Unexcepted Error: {e}")
                    logger.debug(f"Message received from {client_addr} : {request}")
                    
                else:
                    request, used = doip.parse(data)

                    if not routing_activated:
                        if type(request) is doip.RoutingActivationRequest:
                            response = doip.RoutingActivationResponse(request.params['source_address'],
                                                                    self.config['addresses']['discovery'])
                            outdata = response.render()
                            writer.write(outdata)
                            await writer.drain()
                            routing_activated = True
                            continue # to the next incoming packet
                        else:
                            logger.error('Error: Received non-activation request message before activation: %s', request)
                            logger.error('       Closing socket...')
                            break
                    else:
                        if type(request) is doip.DiagnosticMessage:
                            source_address = request.params['source_address']
                            target_address = request.params['target_address']
                            userdata = request.params['userdata']

                            if not self.simulator.has_target_address(target_address):
                                logger.error('Error: target_address 0x{:02x} is unknown'.format(target_address))
                                response = doip.DiagnosticMessageNegativeAck(source_address, target_address,
                                                        doip.DiagnosticMessageNegativeAck.UNKNOWN_TARGET_ADDR)
                                writer.write(response.render())
                                await writer.drain()
                                continue
                            else:
                                response = doip.DiagnosticMessageAck(source_address, target_address)
                                writer.write(response.render())
                                await writer.drain()

                            try:
                                uds_request = uds.parse(userdata)
                                if type(uds_request) is uds.TesterPresent:
                                    uds_reply = uds_request # send it straight back
                                elif type(uds_request) is uds.ReadDataByIdentifier:
                                    identifier = uds_request.params['identifier']
                                    try:
                                        readdata = self.simulator.read_value(target_address, identifier)
                                        uds_reply = uds.ReadDataByIdentifier(identifier, userdata=readdata, is_reply=True)
                                    except sim.IdentifierNotFound as err:
                                        logger.error('Error: %s', str(err))
                                        uds_reply = uds.Error(uds.ReadDataByIdentifier.service_id, uds.Error.REQUEST_OUT_OF_RANGE)
                                else:
                                    logger.error('Service ID 0x{:02x} is not implemented on server'.format(uds_request.service_id))
                                    uds_reply = uds.Error(uds.ReadDataByIdentifier.service_id, uds.Error.SERVICE_NOT_SUPPORTED)
                                response = doip.DiagnosticMessage(source_address, target_address, uds_reply.render(is_reply=True))
                            except uds.ServiceIDNotSupported as err:
                                logger.error('Error: %s', str(err))
                                uds_reply = uds.Error(userdata[0], uds.Error.SERVICE_NOT_SUPPORTED)
                                response = doip.DiagnosticMessage(source_address, target_address, uds_reply.render(is_reply=True))
                            except uds.InvalidMessage as err:
                                logger.error('Error: %s', str(err))
                                uds_reply = uds.Error(userdata[0], uds.Error.INVALID_FORMAT)
                                response = doip.DiagnosticMessage(source_address, target_address, uds_reply.render(is_reply=True))
                            writer.write(response.render())
                            await writer.drain()

        except doip.InvalidMessage as err:
            logger.error(f'Invalid Message is received - {err}')
        except doip.MessageTypeNotSupported as err:
            logger.error(f'Message Type Not Supported - {err}')
        except Exception as err:
            logger.error(f'Error in session with {client_addr}')
        finally:
            writer.close()

    async def restart_tcp_server(self):
        if self.tcp_server:
            self.tcp_server.close()
            await self.tcp_server.wait_closed()
            self.tcp_server = None
            print("Server has been stopped. Restarting now...")
            logger.info("Server has been stopped. Restarting now...")
        await self.start_tcp_server()


######################
#     udp server     #
######################
    async def start_udp_server(self):
        try:
            if not self.loop:
                self.loop = asyncio.get_running_loop()

            self.udp_protocol = EchoUDPProtocol(self.udp_message_handler, self.loop)
            self.udp_transport, _ = await self.loop.create_datagram_endpoint(
                lambda: self.udp_protocol,
                local_addr=(self.host, self.port))
            
            self._should_stop_cnt = 0
            print(f"DoIP Serving on ('{self.host}', {self.port}) by udp...")
            logger.info(f"DoIP Serving on ('{self.host}', {self.port}) by udp...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    # 길이가 100 이상인 데이터가 수신되면 서버를 잠시 종료하고 재시작하도록 모사
    async def udp_message_handler(self, data):
        if (len(data) >= 100):
            self._should_stop_cnt += 1

            try:
                if self._should_stop_cnt == 3:
                    self._should_stop_cnt = 0
                    self.udp_transport.close()  # 현재 udp 서버 소켓 닫기
                    logger.info(f"UDP Server has been stopped. Restarting now...")
                    await asyncio.sleep(5)
                    await self.start_udp_server()  # 비동기적으로 서버 재시작
            except Exception as e:
                logger.error(f"[udp_message_handler] Error: {e}")

class EchoUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, on_con_message, loop):
        self.on_con_message = on_con_message
        self.loop = loop
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if self.on_con_message:
            asyncio.create_task(self.on_con_message(data))