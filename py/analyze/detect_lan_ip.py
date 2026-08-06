import sys

from net_utils import detect_lan_ip


def main():
    print(detect_lan_ip())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"detect_lan_ip failed: {exc}", file=sys.stderr)
        sys.exit(1)
