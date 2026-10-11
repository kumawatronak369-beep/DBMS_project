from packet_capture import PacketCapture


def main():

    print("=" * 60)
    print("NETWORK MONITOR COLLECTOR")
    print("=" * 60)

    capture = PacketCapture()

    capture.start()


if __name__ == "__main__":
    main()