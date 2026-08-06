import ipaddress
import socket
import subprocess


EXCLUDED_INTERFACE_KEYWORDS = (
    "loopback",
    "vmware",
    "virtualbox",
    "vethernet",
    "hyper-v",
    "default switch",
    "bluetooth",
)


def is_usable_lan_ip(ip):
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (
        address.version == 4
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_unspecified
    )


def detect_default_route_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # UDP connect does not send packets; it only asks the OS which local
        # address would be used for a normal outbound route.
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        return ip if is_usable_lan_ip(ip) else None
    except OSError:
        return None
    finally:
        sock.close()


def interface_score(name):
    lower_name = name.lower()
    if any(keyword in lower_name for keyword in EXCLUDED_INTERFACE_KEYWORDS):
        return -100
    if "wlan" in lower_name or "wi-fi" in lower_name or "wifi" in lower_name:
        return 100
    if "ethernet" in lower_name or "以太网" in lower_name:
        return 90
    return 10


def detect_ips_from_powershell():
    command = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        (
            "Get-NetIPAddress -AddressFamily IPv4 | "
            "Where-Object { $_.AddressState -eq 'Preferred' } | "
            "ForEach-Object { \"$($_.InterfaceAlias)|$($_.IPAddress)\" }"
        ),
    ]
    try:
        output = subprocess.check_output(command, text=True, encoding="utf-8", errors="replace")
    except (OSError, subprocess.CalledProcessError):
        return []

    candidates = []
    for line in output.splitlines():
        if "|" not in line:
            continue
        interface_name, ip = line.split("|", 1)
        ip = ip.strip()
        if not is_usable_lan_ip(ip):
            continue
        score = interface_score(interface_name)
        if score < 0:
            continue
        candidates.append((score, interface_name.strip(), ip))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def detect_lan_ip():
    default_ip = detect_default_route_ip()
    if default_ip:
        return default_ip

    candidates = detect_ips_from_powershell()
    if candidates:
        return candidates[0][2]

    raise RuntimeError("No usable LAN IPv4 address found")


def build_chfs_url(port=9527):
    return f"http://{detect_lan_ip()}:{int(port)}"
