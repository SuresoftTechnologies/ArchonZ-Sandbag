# system
from scapy.contrib.automotive.someip import *
from scapy.layers.inet import *

#load_contrib('automotive.someip')

def someip_method_call(msg):
    sip = SOMEIP()
    sip.iface_ver = 1
    sip.proto_ver = 1
    sip.msg_type = "REQUEST"
    sip.retcode = "E_OK"
    sip.srv_id = 0xB0A7
    sip.method_id = 3
    sip.add_payload(Raw(msg))

    pkt = IP(dst="127.0.0.1") / UDP(dport=30509) / sip

    #print(pkt)
    res = sr1(pkt, retry=0, timeout=1, verbose=False)
    print(res)
    res.show()


def someip_sd():
    sip = SOMEIP()
    sip.iface_ver = 1
    sip.proto_ver = 1
    #sip.msg_type = "REQUEST"
    #sip.retcode = "E_OK"
    sip.srv_id = 0xffff
    sip.method_id = 0x8100

    # find service
    ea = SDEntry_Service()
    ea.type = 0x02  # find service
    #[0x00] = FindService
    #[0x01] = OfferService
    #[0x02] = RequestService
    #[0x03] = RequestServiceAck
    #[0x04] = FindEventgroup
    #[0x05] = PublishEventgroup
    #[0x06] = SubscribeEventgroup
    #[0x07] = SubscribeEventgroupAck

    ea.srv_id = 0xb0a7

    ea.inst_id = 0xFFFF # for all
    ea.major_ver = 1


    oa = SDOption_IP4_EndPoint()
    oa.addr = "10.10.111.12"
    oa.l4_proto = 0x11
    oa.port = 30509


    sd = SD()
    sd.set_entryArray(ea)
    sd.set_optionArray(oa)
    sd.build()

    newservice = IP(dst="127.0.0.1") / UDP(dport=30490) / sip / sd
    newservice.show()
    res = sr1(newservice, timeout=1)
    #print(res)
    #res.show()

#someip_sd()
someip_method_call('Peter')