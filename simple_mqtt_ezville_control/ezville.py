import paho.mqtt.client as mqtt
import json
import time
import asyncio
import threading
import telnetlib
import socket
import random

from threading import Thread
from queue import Queue

# DEVICE 별 패킷 정보
RS485_DEVICE = {
    'light': {
        'state':     { 'id': '0E', 'cmd': '81' },

        'power':     { 'id': '0E', 'cmd': '41', 'ack': 'C1' }
    },
#    'thermostat': {
#        'state':     { 'id': '36', 'cmd': '81' },
#
#        'power':     { 'id': '36', 'cmd': '43', 'ack': 'C3' },
#        'away':      { 'id': '36', 'cmd': '45', 'ack': 'C5' },
#        'target':    { 'id': '36', 'cmd': '44', 'ack': 'C4' }
#    },
#    'plug': {
#        'state':     { 'id': '30', 'cmd': '81' },
#
#        'power':     { 'id': '30', 'cmd': '41', 'ack': 'C1' }
#    },
#    'gasvalve': {
#        'state':     { 'id': '12', 'cmd': '81' },
#
#        'power':     { 'id': '12', 'cmd': '41', 'ack': 'C1' } # 잠그기만 가능
#    },
#    'batch': {
#        'state':     { 'id': '33', 'cmd': '81' },
#
#        'press':     { 'id': '33', 'cmd': '41', 'ack': 'C1' }
#    }
}

# MQTT Discovery를 위한 Preset 정보
DISCOVERY_DEVICE = {
    'ids': ['ezville_wallpad',],
    'name': 'ezville_wallpad',
    'mf': 'EzVille',
    'mdl': 'EzVille Wallpad',
    'sw': 'ktdo79/addons/ezville_wallpad',
}

# MQTT Discovery를 위한 Payload 정보
DISCOVERY_PAYLOAD = {
    'light': [ {
        '_intg': 'light',
        '~': 'ezville/light_{:0>2d}_{:0>2d}',
        'name': 'ezville_light_{:0>2d}_{:0>2d}',
        'opt': True,
        'stat_t': '~/power/state',
        'cmd_t': '~/power/command'
    } ],
#    'thermostat': [ {
#        '_intg': 'climate',
#        '~': 'ezville/thermostat_{:0>2d}_{:0>2d}',
#        'name': 'ezville_thermostat_{:0>2d}_{:0>2d}',
#        'mode_cmd_t': '~/power/command',
#        'mode_stat_t': '~/power/state',
#        'temp_stat_t': '~/setTemp/state',
#        'temp_cmd_t': '~/setTemp/command',
#        'curr_temp_t': '~/curTemp/state',
##        "modes": [ "off", "heat", "fan_only" ],     # 외출 모드는 fan_only로 매핑
#        'modes': [ 'heat', 'off' ],     # 외출 모드는 off로 매핑
#        'min_temp': '5',
#        'max_temp': '40'
#    } ],
#    'plug': [ {
#        '_intg': 'switch',
#        '~': 'ezville/plug_{:0>2d}_{:0>2d}',
#        'name': 'ezville_plug_{:0>2d}_{:0>2d}',
#        'stat_t': '~/power/state',
#        'cmd_t': '~/power/command',
#        'icon': 'mdi:leaf'
#    },
#    {
#        '_intg': 'binary_sensor',
#        '~': 'ezville/plug_{:0>2d}_{:0>2d}',
#        'name': 'ezville_plug-automode_{:0>2d}_{:0>2d}',
#        'stat_t': '~/auto/state',
#        'icon': 'mdi:leaf'
#    },
#    {
#        '_intg': 'sensor',
#        '~': 'ezville/plug_{:0>2d}_{:0>2d}',
#        'name': 'ezville_plug_{:0>2d}_{:0>2d}_powermeter',
#        'stat_t': '~/current/state',
#        'unit_of_meas': 'W'
#    } ],
#    'gasvalve': [ {
#        '_intg': 'switch',
#        '~': 'ezville/gasvalve_{:0>2d}_{:0>2d}',
#        'name': 'ezville_gasvalve_{:0>2d}_{:0>2d}',
#        'stat_t': '~/power/state',
#        'cmd_t': '~/power/command',
#        'icon': 'mdi:valve'
#    } ],
#    'batch': [ {
#        '_intg': 'button',
#        '~': 'ezville/batch_{:0>2d}_{:0>2d}',
#        'name': 'ezville_batch-elevator-up_{:0>2d}_{:0>2d}',
#        'cmd_t': '~/elevator-up/command',
#        'icon': 'mdi:elevator-up'
#    },
#    {
#        '_intg': 'button',
#        '~': 'ezville/batch_{:0>2d}_{:0>2d}',
#        'name': 'ezville_batch-elevator-down_{:0>2d}_{:0>2d}',
#        'cmd_t': '~/elevator-down/command',
#        'icon': 'mdi:elevator-down'
#    },
#    {
#        '_intg': 'binary_sensor',
#        '~': 'ezville/batch_{:0>2d}_{:0>2d}',
#        'name': 'ezville_batch-groupcontrol_{:0>2d}_{:0>2d}',
#        'stat_t': '~/group/state',
#        'icon': 'mdi:lightbulb-group'
#    },
#    {
#        '_intg': 'binary_sensor',
#        '~': 'ezville/batch_{:0>2d}_{:0>2d}',
#        'name': 'ezville_batch-outing_{:0>2d}_{:0>2d}',
#        'stat_t': '~/outing/state',
#        'icon': 'mdi:home-circle'
#    } ]
}

# STATE 확인용 Dictionary
STATE_HEADER = {
    prop['state']['id']: (device, prop['state']['cmd'])
    for device, prop in RS485_DEVICE.items()
    if 'state' in prop
}

# ACK 확인용 Dictionary
ACK_HEADER = {
    prop[cmd]['id']: (device, prop[cmd]['ack'])
    for device, prop in RS485_DEVICE.items()
        for cmd, code in prop.items()
            if 'ack' in code
}

# LOG 메시지
def log(string):
    date = time.strftime('%Y-%m-%d %p %I:%M:%S', time.localtime(time.time()))
    print('[{}] {}'.format(date, string))
    return

# CHECKSUM 및 ADD를 마지막 4 BYTE에 추가
def checksum(input_hex):
    try:
        input_hex = input_hex[:-4]

        # 문자열 bytearray로 변환
        packet = bytes.fromhex(input_hex)

        # checksum 생성
        checksum = 0
        for b in packet:
            checksum ^= b

        # add 생성
        add = (sum(packet) + checksum) & 0xFF

        # checksum add 합쳐서 return
        return input_hex + format(checksum, '02X') + format(add, '02X')
    except:
        return None


config_dir = '/data'

HA_TOPIC = 'ezville'
STATE_TOPIC = HA_TOPIC + '/{}/{}/state'
EW11_TOPIC = 'ew11'
EW11_SEND_TOPIC = EW11_TOPIC + '/send'


# Main Function
def ezville_loop(config):

    # Log 생성 Flag
    debug = config['DEBUG_LOG']
    mqtt_log = config['MQTT_LOG']
    ew11_log = config['EW11_LOG']

    # 통신 모드 설정: mixed, socket, mqtt
    comm_mode = config['mode']

    # Socket 정보
    SOC_ADDRESS = config['ew11_server']
    SOC_PORT = config['ew11_port']

    # EW11 혹은 HA 전달 메시지 저장소
    MSG_QUEUE = Queue()

    # EW11에 보낼 Command 및 예상 Acknowledge 패킷
    CMD_QUEUE = asyncio.Queue()

    # State 저장용 공간
    DEVICE_STATE = {}

    # 이전에 전달된 패킷인지 판단을 위한 캐쉬
    MSG_CACHE = {}

    # MQTT Discovery Que
    DISCOVERY_DELAY = config['discovery_delay']
    DISCOVERY_LIST = []

    # EW11 전달 패킷 중 처리 후 남은 짜투리 패킷 저장
    RESIDUE = ''

    # 강제 주기적 업데이트 설정 - 매 force_update_period 마다 force_update_duration초간 HA 업데이트 실시
    FORCE_UPDATE = False
    FORCE_MODE = config['force_update_mode']
    FORCE_PERIOD = config['force_update_period']
    FORCE_DURATION = config['force_update_duration']

    # Command를 EW11로 보내는 방식 설정 (동시 명령 횟수, 명령 간격 및 재시도 횟수)
    CMD_INTERVAL = config['command_interval']
    CMD_RETRY_COUNT = config['command_retry_count']
    FIRST_WAITTIME = config['first_waittime']
    RANDOM_BACKOFF = config['random_backoff']

    # State 업데이트 루프 / Command 실행 루프 / Socket 통신으로 패킷 받아오는 루프 / Restart 필요한지 체크하는 루프의 Delay Time 설정
    STATE_LOOP_DELAY = config['state_loop_delay']
    COMMAND_LOOP_DELAY = config['command_loop_delay']
    SERIAL_RECV_DELAY = config['serial_recv_delay']
    RESTART_CHECK_DELAY = config['restart_check_delay']

    # EW11에 설정된 BUFFER SIZE
    EW11_BUFFER_SIZE = config['ew11_buffer_size']

    # EW11 동작상태 확인용 메시지 수신 시간 체크 주기 및 체크용 시간 변수
    EW11_TIMEOUT = config['ew11_timeout']
    last_received_time = time.time()

    # EW11 재시작 확인용 Flag
    restart_flag = False

    # MQTT Integration 활성화 확인 Flag - 단, 사용을 위해서는 MQTT Integration에서 Birth/Last Will Testament 설정 및 Retain 설정 필요
    MQTT_ONLINE = False

    # Addon 정상 시작 Flag
    ADDON_STARTED = False

    # Reboot 이후 안정적인 동작을 위한 제어 Flag
    REBOOT_CONTROL = config['reboot_control']
    REBOOT_DELAY = config['reboot_delay']

    # 시작 시 인위적인 Delay 필요시 사용
    startup_delay = 0


    # MQTT 통신 연결 Callback
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            log('[INFO] MQTT Broker 연결 성공')
            # Socket인 경우 MQTT 장치의 명령 관련과 MQTT Status (Birth/Last Will Testament) Topic만 구독
            if comm_mode == 'socket':
                client.subscribe([(HA_TOPIC + '/#', 0), ('homeassistant/status', 0)])
            # Mixed인 경우 MQTT 장치 및 EW11의 명령/수신 관련 Topic 과 MQTT Status (Birth/Last Will Testament) Topic 만 구독
            elif comm_mode == 'mixed':
                client.subscribe([(HA_TOPIC + '/#', 0), (EW11_TOPIC + '/recv', 0), ('homeassistant/status', 0)])
            # MQTT 인 경우 모든 Topic 구독
            else:
                client.subscribe([(HA_TOPIC + '/#', 0), (EW11_TOPIC + '/recv', 0), (EW11_TOPIC + '/send', 1), ('homeassistant/status', 0)])
        else:
            errcode = {1: 'Connection refused - incorrect protocol version',
                       2: 'Connection refused - invalid client identifier',
                       3: 'Connection refused - server unavailable',
                       4: 'Connection refused - bad username or password',
                       5: 'Connection refused - not authorised'}
            log(errcode[rc])


    # MQTT 메시지 Callback
    def on_message(client, userdata, msg):
        nonlocal MSG_QUEUE
        nonlocal MQTT_ONLINE
        nonlocal startup_delay

        if msg.topic == 'homeassistant/status':
            # Reboot Control 사용 시 MQTT Integration의 Birth/Last Will Testament Topic은 바로 처리
            if REBOOT_CONTROL:
                status = msg.payload.decode('utf-8')

                if status == 'online':
                    log('[INFO] MQTT Integration 온라인')
                    MQTT_ONLINE = True
                    if not msg.retain:
                        log('[INFO] MQTT Birth Message가 Retain이 아니므로 정상화까지 Delay 부여')
                        startup_delay = REBOOT_DELAY
                elif status == 'offline':
                    log('[INFO] MQTT Integration 오프라인')
                    MQTT_ONLINE = False
        # 나머지 topic은 모두 Queue에 보관
        else:
            MSG_QUEUE.put(msg)


    # MQTT 통신 연결 해제 Callback
    def on_disconnect(client, userdata, rc):
        log('INFO: MQTT 연결 해제')
        pass


    # MQTT message를 분류하여 처리
    async def process_message():
        # MSG_QUEUE의 message를 하나씩 pop
        nonlocal MSG_QUEUE
        nonlocal last_received_time

        stop = False
        while not stop:
            if MSG_QUEUE.empty():
                stop = True
            else:
                msg = MSG_QUEUE.get()
                topics = msg.topic.split('/')

                if topics[0] == HA_TOPIC and topics[-1] == 'command':
                    await HA_process(topics, msg.payload.decode('utf-8'))
                elif topics[0] == EW11_TOPIC and topics[-1] == 'recv':
                    # Que에서 확인된 시간 기준으로 EW11 Health Check함.
                    last_received_time = time.time()

                    await EW11_process(msg.payload.hex().upper())


    # EW11 전달된 메시지 처리
    async def EW11_process(raw_data):
        nonlocal DISCOVERY_LIST
        nonlocal RESIDUE
        nonlocal MSG_CACHE
        nonlocal DEVICE_STATE

        raw_data = RESIDUE + raw_data

        if ew11_log:
            log('[SIGNAL] receved: {}'.format(raw_data))

        k = 0
        cors = []
        msg_length = len(raw_data)
        while k < msg_length:
            # F7로 시작하는 패턴을 패킷으로 분리
            if raw_data[k:k + 2] == 'F7':
                # 남은 데이터가 최소 패킷 길이를 만족하지 못하면 RESIDUE에 저장 후 종료
                if k + 10 > msg_length:
                    RESIDUE = raw_data[k:]
                    break
                else:
                    data_length = int(raw_data[k + 8:k + 10], 16)
                    packet_length = 10 + data_length * 2 + 4

                    # 남은 데이터가 예상되는 패킷 길이보다 짧으면 RESIDUE에 저장 후 종료
                    if k + packet_length > msg_length:
                        RESIDUE = raw_data[k:]
                        break
                    else:
                        packet = raw_data[k:k + packet_length]

                # 분리된 패킷이 Valid한 패킷인지 Checksum 확인
                if packet != checksum(packet):
                    k+=1
                    continue
                else:
                    STATE_PACKET = False
                    ACK_PACKET = False

                    # STATE 패킷인지 확인
                    if packet[2:4] in STATE_HEADER and packet[6:8] in STATE_HEADER[packet[2:4]][1]:
                        STATE_PACKET = True
                    # ACK 패킷인지 확인
                    elif packet[2:4] in ACK_HEADER and packet[6:8] in ACK_HEADER[packet[2:4]][1]:
                        ACK_PACKET = True

                    if STATE_PACKET or ACK_PACKET:
                        # MSG_CACHE에 없는 새로운 패킷이거나 FORCE_UPDATE 실행된 경우만 실행
                        if MSG_CACHE.get(packet[0:10]) != packet[10:] or FORCE_UPDATE:
                            name = STATE_HEADER[packet[2:4]][0]
                            if name == 'light':
                                # ROOM ID
                                rid = int(packet[5], 16)
                                # ROOM의 light 갯수 + 1
                                slc = int(packet[8:10], 16)

                                for id in range(1, slc):
                                    discovery_name = '{}_{:0>2d}_{:0>2d}'.format(name, rid, id)

                                    if discovery_name not in DISCOVERY_LIST:
                                        DISCOVERY_LIST.append(discovery_name)

                                        payload = DISCOVERY_PAYLOAD[name][0].copy()
                                        payload['~'] = payload['~'].format(rid, id)
                                        payload['name'] = payload['name'].format(rid, id)

                                        # 장치 등록 후 DISCOVERY_DELAY초 후에 State 업데이트
                                        await mqtt_discovery(payload)
                                        await asyncio.sleep(DISCOVERY_DELAY)

                                    # State 업데이트까지 진행
                                    onoff = 'ON' if int(packet[10 + 2 * id: 12 + 2 * id], 16) & 1 else 'OFF'

                                    await update_state(name, 'power', rid, id, onoff)

                                    # 직전 처리 State 패킷은 저장
                                    if STATE_PACKET:
                                        MSG_CACHE[packet[0:10]] = packet[10:]
#                            elif name == 'thermostat':
#                                # room 갯수
#                                rc = int((int(packet[8:10], 16) - 5) / 2)
#                                # room의 조절기 수 (현재 하나 뿐임)
#                                src = 1
#
#                                onoff_state = bin(int(packet[12:14], 16))[2:].zfill(8)
#                                away_state = bin(int(packet[14:16], 16))[2:].zfill(8)
#
#                                for rid in range(1, rc + 1):
#                                    discovery_name = '{}_{:0>2d}_{:0>2d}'.format(name, rid, src)
#
#                                    if discovery_name not in DISCOVERY_LIST:
#                                        DISCOVERY_LIST.append(discovery_name)
#
#                                        payload = DISCOVERY_PAYLOAD[name][0].copy()
#                                        payload['~'] = payload['~'].format(rid, src)
#                                        payload['name'] = payload['name'].format(rid, src)
#
#                                        # 장치 등록 후 DISCOVERY_DELAY초 후에 State 업데이트
#                                        await mqtt_discovery(payload)
#                                        await asyncio.sleep(DISCOVERY_DELAY)
#
#                                    setT = str(int(packet[16 + 4 * rid:18 + 4 * rid], 16))
#                                    curT = str(int(packet[18 + 4 * rid:20 + 4 * rid], 16))
#
#                                    if onoff_state[8 - rid ] == '1':
#                                        onoff = 'heat'
#                                    # 외출 모드는 off로
#                                    elif onoff_state[8 - rid] == '0' and away_state[8 - rid] == '1':
#                                        onoff = 'off'
##                                    elif onoff_state[8 - rid] == '0' and away_state[8 - rid] == '0':
##                                        onoff = 'off'
##                                    else:
##                                        onoff = 'off'
#
#                                    await update_state(name, 'power', rid, src, onoff)
#                                    await update_state(name, 'curTemp', rid, src, curT)
#                                    await update_state(name, 'setTemp', rid, src, setT)
#
#                                    # 직전 처리 State 패킷은 저장
#                                    if STATE_PACKET:
#                                        MSG_CACHE[packet[0:10]] = packet[10:]
#                                    else:
#                                        # Ack 패킷도 State로 저장
#                                        MSG_CACHE['F7361F810F'] = packet[10:]
#
#                            # plug는 ACK PACKET에 상태 정보가 없으므로 STATE_PACKET만 처리
#                            elif name == 'plug' and STATE_PACKET:
#                                if STATE_PACKET:
#                                    # ROOM ID
#                                    rid = int(packet[5], 16)
#                                    # ROOM의 plug 갯수
#                                    spc = int(packet[10:12], 16)
#
#                                    for id in range(1, spc + 1):
#                                        discovery_name = '{}_{:0>2d}_{:0>2d}'.format(name, rid, id)
#
#                                        if discovery_name not in DISCOVERY_LIST:
#                                            DISCOVERY_LIST.append(discovery_name)
#
#                                            for payload_template in DISCOVERY_PAYLOAD[name]:
#                                                payload = payload_template.copy()
#                                                payload['~'] = payload['~'].format(rid, id)
#                                                payload['name'] = payload['name'].format(rid, id)
#
#                                                # 장치 등록 후 DISCOVERY_DELAY초 후에 State 업데이트
#                                                await mqtt_discovery(payload)
#                                                await asyncio.sleep(DISCOVERY_DELAY)
#
#                                    # BIT0: 대기전력 On/Off, BIT1: 자동모드 On/Off
#                                    # 위와 같지만 일단 on-off 여부만 판단
#                                    DATA = "{0:024b}".format(int(packet[6 + 6 * id : 12 + 6 * id], 16))
#                                    onoff = "ON" if DATA[3] == "1" else "OFF"
#                                    autoonoff = "ON" if DATA[0] == "1" else "OFF"
#                                    current = DATA[4:]
#                                    power_num = "{:.1f}".format(
#                                        sum(
#                                            int(x, 2) * pow(10, 3 - i)
#                                            for i, x in enumerate(
#                                                [
#                                                    current[i : i + 4]
#                                                    for i in range(
#                                                        0, len(current), 4
#                                                    )
#                                                ]
#                                            )
#                                        )
#                                    )
#
#                                    await update_state(
#                                        name, "power", rid, id, onoff
#                                    )
#                                    await update_state(
#                                        name, "auto", rid, id, autoonoff
#                                    )
#                                    await update_state(
#                                        name, "current", rid, id, power_num
#                                    )
#
#                                    # 직전 처리 State 패킷은 저장
#                                    MSG_CACHE[packet[0:10]] = packet[10:]
#                                else:
#                                    # ROOM ID
#                                    rid = int(packet[5], 16)
#                                    # ROOM의 plug 갯수
#                                    sid = int(packet[10:12], 16)
#
#                                    onoff = 'ON' if int(packet[13], 16) > 0 else 'OFF'
#
#                                    await update_state(name, 'power', rid, id, onoff)
#
#                            elif name == 'gasvalve':
#                                # Gas Value는 하나라서 강제 설정
#                                rid = 1
#                                # Gas Value는 하나라서 강제 설정
#                                spc = 1
#
#                                discovery_name = '{}_{:0>2d}_{:0>2d}'.format(name, rid, spc)
#
#                                if discovery_name not in DISCOVERY_LIST:
#                                    DISCOVERY_LIST.append(discovery_name)
#
#                                    payload = DISCOVERY_PAYLOAD[name][0].copy()
#                                    payload['~'] = payload['~'].format(rid, spc)
#                                    payload['name'] = payload['name'].format(rid, spc)
#
#                                    # 장치 등록 후 DISCOVERY_DELAY초 후에 State 업데이트
#                                    await mqtt_discovery(payload)
#                                    await asyncio.sleep(DISCOVERY_DELAY)
#
#                                onoff = 'ON' if int(packet[12:14], 16) == 1 else 'OFF'
#
#                                await update_state(name, 'power', rid, spc, onoff)
#
#                                # 직전 처리 State 패킷은 저장
#                                if STATE_PACKET:
#                                    MSG_CACHE[packet[0:10]] = packet[10:]
#
#                            # 일괄차단기 ACK PACKET은 상태 업데이트에 반영하지 않음
#                            elif name == 'batch' and STATE_PACKET:
#                                # 일괄차단기는 하나라서 강제 설정
#                                rid = 1
#                                # 일괄차단기는 하나라서 강제 설정
#                                sbc = 1
#
#                                discovery_name = '{}_{:0>2d}_{:0>2d}'.format(name, rid, sbc)
#
#                                if discovery_name not in DISCOVERY_LIST:
#                                    DISCOVERY_LIST.append(discovery_name)
#
#                                    for payload_template in DISCOVERY_PAYLOAD[name]:
#                                        payload = payload_template.copy()
#                                        payload['~'] = payload['~'].format(rid, sbc)
#                                        payload['name'] = payload['name'].format(rid, sbc)
#
#                                        # 장치 등록 후 DISCOVERY_DELAY초 후에 State 업데이트
#                                        await mqtt_discovery(payload)
#                                        await asyncio.sleep(DISCOVERY_DELAY)
#
#                                # 일괄 차단기는 버튼 상태 변수 업데이트
#                                states = bin(int(packet[12:14], 16))[2:].zfill(8)
#
#                                ELEVDOWN = states[2]
#                                ELEVUP = states[3]
#                                GROUPON = states[5]
#                                OUTING = states[6]
#
#                                grouponoff = 'ON' if GROUPON == '1' else 'OFF'
#                                outingonoff = 'ON' if OUTING == '1' else 'OFF'
#
#                                #ELEVDOWN과 ELEVUP은 직접 DEVICE_STATE에 저장
#                                elevdownonoff = 'ON' if ELEVDOWN == '1' else 'OFF'
#                                elevuponoff = 'ON' if ELEVUP == '1' else 'OFF'
#                                DEVICE_STATE['batch_01_01elevator-up'] = elevuponoff
#                                DEVICE_STATE['batch_01_01elevator-down'] = elevdownonoff
#
#                                # 일괄 조명 및 외출 모드는 상태 업데이트
#                                await update_state(name, 'group', rid, sbc, grouponoff)
#                                await update_state(name, 'outing', rid, sbc, outingonoff)
#
#                                MSG_CACHE[packet[0:10]] = packet[10:]

                    RESIDUE = ''
                    k = k + packet_length

            else:
                k+=1


    # MQTT Discovery로 장치 자동 등록
    async def mqtt_discovery(payload):
        intg = payload.pop('_intg')

        # MQTT 통합구성요소에 등록되기 위한 추가 내용
        payload['device'] = DISCOVERY_DEVICE
        payload['uniq_id'] = payload['name']

        # Discovery에 등록
        topic = 'homeassistant/{}/ezville_wallpad/{}/config'.format(intg, payload['name'])
        log('[INFO] 장치 등록:  {}'.format(topic))
        mqtt_client.publish(topic, json.dumps(payload))


    # 장치 State를 MQTT로 Publish
    async def update_state(device, state, id1, id2, value):
        nonlocal DEVICE_STATE

        deviceID = '{}_{:0>2d}_{:0>2d}'.format(device, id1, id2)
        key = deviceID + state

        if value != DEVICE_STATE.get(key) or FORCE_UPDATE:
            DEVICE_STATE[key] = value

            topic = STATE_TOPIC.format(deviceID, state)
            mqtt_client.publish(topic, value.encode())

            if mqtt_log:
                log('[LOG] ->> HA : {} >> {}'.format(topic, value))

        return


    # HA에서 전달된 메시지 처리
    async def HA_process(topics, value):
        nonlocal CMD_QUEUE

        device_info = topics[1].split('_')
        device = device_info[0]

        if mqtt_log:
            log('[LOG] HA ->> : {} -> {}'.format('/'.join(topics), value))

        if device in RS485_DEVICE:
            key = topics[1] + topics[2]
            idx = int(device_info[1])
            sid = int(device_info[2])
            cur_state = DEVICE_STATE.get(key)

            if value == cur_state:
                pass

            else:
                if device == 'thermostat':
                    if topics[2] == 'power':
                        if value == 'heat':

                            sendcmd = checksum('F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['cmd'] + '01010000')
                            recvcmd = 'F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['ack']
                            statcmd = [key, value]

                            await CMD_QUEUE.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})

                        # Thermostat는 외출 모드를 Off 모드로 연결
                        elif value == 'off':

                            sendcmd = checksum('F7' + RS485_DEVICE[device]['away']['id'] + '1' + str(idx) + RS485_DEVICE[device]['away']['cmd'] + '01010000')
                            recvcmd = 'F7' + RS485_DEVICE[device]['away']['id'] + '1' + str(idx) + RS485_DEVICE[device]['away']['ack']
                            statcmd = [key, value]

                            await CMD_QUEUE.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})

#                        elif value == 'off':
#
#                            sendcmd = checksum('F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['cmd'] + '01000000')
#                            recvcmd = 'F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['ack']
#                            statcmd = [key, value]
#
#                            await CMD_QUEUE.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})
                                                        

                        if debug:
                            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))

                    elif topics[2] == 'setTemp':
                        value = int(float(value))

                        sendcmd = checksum('F7' + RS485_DEVICE[device]['target']['id'] + '1' + str(idx) + RS485_DEVICE[device]['target']['cmd'] + '01' + "{:02X}".format(value) + '0000')
                        recvcmd = 'F7' + RS485_DEVICE[device]['target']['id'] + '1' + str(idx) + RS485_DEVICE[device]['target']['ack']
                        statcmd = [key, str(value)]

                        await CMD_QUEUE.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})

                        if debug:
                            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))

#                elif device == 'Fan':
#                    if topics[2] == 'power':
#                        sendcmd = DEVICE_LISTS[device][idx].get('command' + value)
#                        recvcmd = DEVICE_LISTS[device][idx.get('receive' + value)
#                        statcmd = [key, value]
#
#                        await CMD_QUEUE.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})
#
#                        if debug:
#                            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))

                elif device == 'light':
                    if topics[2] == 'power':
                        value = '01' if value == 'ON' else '00'

                        sendcmd = checksum('F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['cmd'] + "{:02X}".format(sid) + value + '0000')
                        recvcmd = 'F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['ack']
                        statcmd = [key, 'ON' if value == '01' else 'OFF']

                        await CMD_QUEUE.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})

                        if debug:
                            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))

                elif device == 'plug':
                    if topics[2] == 'power':
                        value = '01' if value == 'ON' else '00'

                        sendcmd = checksum('F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['cmd'] + "{:02X}".format(sid) + value + '0000')
                        recvcmd = 'F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['ack']
                        statcmd = [key, 'ON' if value == '01' else 'OFF']

                        await CMD_QUEUE.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})

                        if debug:
                            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))

                elif device == 'gasvalve':
                    if topics[2] == 'power':
                        value = '01' if value == 'ON' else '00' # 잠그기만 가능

                        sendcmd = checksum('F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['cmd'] + "{:02X}".format(sid) + value + '0000')
                        recvcmd = 'F7' + RS485_DEVICE[device]['power']['id'] + '1' + str(idx) + RS485_DEVICE[device]['power']['ack']
                        statcmd = [key, 'ON' if value == '01' else 'OFF']

                        await CMD_QUEUE.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})

                        if debug:
                            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))

                elif device == 'batch':
                    if topics[2] == 'elevator-up':
                        sendcmd = checksum('F7' + RS485_DEVICE[device]['press']['id'] + '1' + str(idx) + RS485_DEVICE[device]['press']['cmd'] + '04010000')
                        recvcmd = 'F7' + RS485_DEVICE[device]['press']['id'] + '1' + str(idx) + RS485_DEVICE[device]['press']['ack']
                        statcmd = [key, value]

                        await CMD_QUEUE.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})

                        if debug:
                            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))
                    elif topics[2] == 'elevator-down':
                        sendcmd = checksum('F7' + RS485_DEVICE[device]['press']['id'] + '1' + str(idx) + RS485_DEVICE[device]['press']['cmd'] + '08010000')
                        recvcmd = 'F7' + RS485_DEVICE[device]['press']['id'] + '1' + str(idx) + RS485_DEVICE[device]['press']['ack']
                        statcmd = [key, value]

                        await CMD_QUEUE.put({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'statcmd': statcmd})

                        if debug:
                            log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}, statcmd: {}'.format(sendcmd, recvcmd, statcmd))


    # EW11 Serial 통신
    async def ew11_serial_process():
        nonlocal CMD_QUEUE
        nonlocal restart_flag
        nonlocal last_received_time

        await asyncio.sleep(FIRST_WAITTIME)

        while True:
            try:
                if comm_mode == 'socket':
                    reader, writer = await asyncio.open_connection(SOC_ADDRESS, SOC_PORT)
                    log('[INFO] EW11 Socket 연결 성공')
                    break
                else:
                    break
            except Exception as e:
                log('[ERROR] EW11 Socket 연결 실패: {}'.format(e))
                await asyncio.sleep(5)
                continue

        while True:
            try:
                # EW11 Health Check - EW11_TIMEOUT 시간 이상 응답이 없으면 재시작 Flag 설정
                if (time.time() - last_received_time) > EW11_TIMEOUT and ADDON_STARTED:
                    if not restart_flag:
                        log('[ERROR] EW11 응답 없음. 재시작 필요')
                        restart_flag = True
                    await asyncio.sleep(1)
                    continue

                if not CMD_QUEUE.empty():
                    cmd = await CMD_QUEUE.get()
                    send_packet = cmd['sendcmd']
                    expected_ack = cmd['recvcmd']
                    state_command = cmd['statcmd']

                    for retry in range(CMD_RETRY_COUNT + 1):
                        if ew11_log:
                            log('[SIGNAL] send: {}'.format(send_packet))

                        if comm_mode == 'socket':
                            writer.write(bytes.fromhex(send_packet))
                            await writer.drain()

                            response = await asyncio.wait_for(reader.read(EW11_BUFFER_SIZE), timeout=5)
                            recv_packet = response.hex().upper()

                            if ew11_log:
                                log('[SIGNAL] received: {}'.format(recv_packet))

                            if expected_ack in recv_packet:
                                device_info = state_command[0].split('_')
                                await update_state(device_info[0], device_info[2], int(device_info[1]), int(device_info[3]), state_command[1])
                                break
                            elif retry < CMD_RETRY_COUNT:
                                await asyncio.sleep(CMD_INTERVAL + random.uniform(0, RANDOM_BACKOFF))
                            else:
                                log('[ERROR] Command 전송 실패 ({}): {} -> {}'.format(retry + 1, send_packet, recv_packet))

                        elif comm_mode == 'mqtt':
                            mqtt_client.publish(EW11_SEND_TOPIC, bytes.fromhex(send_packet))
                            await asyncio.sleep(CMD_INTERVAL + random.uniform(0, RANDOM_BACKOFF)) # MQTT는 응답 처리가 다르므로 대기 후 넘어감
                            break # MQTT 모드에서는 재시도 로직을 별도로 구현할 수 있음
                        else: # mixed mode
                            # mixed 모드에서는 EW11/send 토픽을 통해 명령 전송
                            mqtt_client.publish(EW11_SEND_TOPIC, bytes.fromhex(send_packet))
                            await asyncio.sleep(CMD_INTERVAL + random.uniform(0, RANDOM_BACKOFF)) # MQTT publish 후 약간의 대기
                            break # mixed 모드에서는 재시도 로직을 별도로 구현할 수 있음

                await asyncio.sleep(COMMAND_LOOP_DELAY)

            except asyncio.CancelledError:
                log('[INFO] EW11 Serial Task 종료')
                break
            except Exception as e:
                log('[ERROR] EW11 Serial 통신 오류: {}'.format(e))
                if comm_mode == 'socket':
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception as close_e:
                        log('[ERROR] Socket 닫기 오류: {}'.format(close_e))
                    # 재연결 시도
                    while True:
                        try:
                            reader, writer = await asyncio.open_connection(SOC_ADDRESS, SOC_PORT)
                            log('[INFO] EW11 Socket 재연결 성공')
                            break
                        except Exception as reconnect_e:
                            log('[ERROR] EW11 Socket 재연결 실패: {}'.format(reconnect_e))
                            await asyncio.sleep(5)
                            continue
                await asyncio.sleep(5)
                continue


    # 주기적인 State Update
    async def state_update_loop():
        nonlocal FORCE_UPDATE
        nonlocal last_received_time
        nonlocal ADDON_STARTED

        if startup_delay > 0:
            log(f'[INFO] 시작 지연 {startup_delay}초')
            await asyncio.sleep(startup_delay)
            startup_delay = 0
            ADDON_STARTED = True
        elif not ADDON_STARTED and not REBOOT_CONTROL:
            ADDON_STARTED = True
            log('[INFO] Addon 시작 완료')

        while True:
            try:
                # EW11 Health Check - 주기적으로 F700018101010000 패킷 전송하여 상태 확인 (매 5분)
                if (time.time() - last_received_time) > EW11_TIMEOUT * 0.5 and ADDON_STARTED and comm_mode == 'socket':
                    health_check_packet = checksum('F700018101010000')
                    if ew11_log:
                        log('[SIGNAL] Health Check Send: {}'.format(health_check_packet))
                    try:
                        writer.write(bytes.fromhex(health_check_packet))
                        await writer.drain()
                    except Exception as e:
                        log('[ERROR] Health Check 패킷 전송 오류: {}'.format(e))

                if FORCE_MODE == 'periodic':
                    FORCE_UPDATE = True
                    log('[INFO] 강제 State 업데이트 시작 ({:.1f}초)".format(FORCE_DURATION))
                    await asyncio.sleep(FORCE_DURATION)
                    FORCE_UPDATE = False
                    log('[INFO] 강제 State 업데이트 종료. 다음 업데이트까지 {:.1f}초 대기".format(FORCE_PERIOD))
                    await asyncio.sleep(FORCE_PERIOD)
                elif FORCE_MODE == 'once':
                    FORCE_UPDATE = True
                    log('[INFO] 1회 강제 State 업데이트 시작 ({:.1f}초)".format(FORCE_DURATION))
                    await asyncio.sleep(FORCE_DURATION)
                    FORCE_UPDATE = False
                    FORCE_MODE = 'off'
                    log('[INFO] 1회 강제 State 업데이트 종료')
                else:
                    await asyncio.sleep(STATE_LOOP_DELAY)
            except asyncio.CancelledError:
                log('[INFO] State Update Task 종료')
                break
            except Exception as e:
                log('[ERROR] State Update Loop 오류: {}'.format(e))
                await asyncio.sleep(5)
                continue

    # 재시작 필요 여부 확인
    async def restart_check_loop():
        nonlocal restart_flag

        while True:
            if restart_flag:
                log('[WARNING] 시스템 재시작 요청')
                # Home Assistant Add-on 재시작 요청 신호
                try:
                    with open('/tmp/restart', 'w') as f:
                        f.write('restart')
                    log('[INFO] 재시작 요청 파일 생성')
                except Exception as e:
                    log('[ERROR] 재시작 요청 파일 생성 실패: {}'.format(e))
                restart_flag = False # 재시작 요청 후 Flag 초기화

            await asyncio.sleep(RESTART_CHECK_DELAY)
            continue

    # 메인 루프
    async def main():
        tasks = [
            asyncio.create_task(process_message()),
            asyncio.create_task(ew11_serial_process()),
            asyncio.create_task(state_update_loop()),
            asyncio.create_task(restart_check_loop())
        ]
        await asyncio.gather(*tasks)

    # MQTT 클라이언트 설정 및 시작
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.connect_async(config['mqtt_server'], config['mqtt_port'], 60)
    mqtt_client.loop_start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log('[INFO] 프로그램 종료')
    finally:
        mqtt_client.loop_stop()
        if comm_mode == 'socket':
            try:
                writer.close()
                asyncio.get_event_loop().run_until_complete(writer.wait_closed())
            except Exception as e:
                log('[ERROR] Socket 닫기 오류 (종료 시): {}'.format(e))log('[INFO] MQTT 클라이언트 종료')
