"""Run: python -m pip install grpcio; python read_health.py"""

import struct

import grpc


def varint(data, offset):
    value = 0
    for shift in range(0, 70, 7):
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError("Invalid protobuf varint")


def field(data, number, wire):
    offset = 0
    while offset < len(data):
        tag, offset = varint(data, offset)
        kind = tag & 7
        if kind == 0:
            _, offset = varint(data, offset)
            continue
        if kind == 2:
            size, offset = varint(data, offset)
        elif kind in (1, 5):
            size = 8 if kind == 1 else 4
        else:
            raise ValueError(f"Unsupported protobuf wire type {kind}")
        if tag >> 3 == number and kind == wire:
            return data[offset : offset + size]
        offset += size


def main():
    with grpc.insecure_channel("127.0.0.1:2942") as channel:
        grpc.channel_ready_future(channel).result(timeout=5)
        stream = channel.unary_stream(
            "/sc.game.telemetry.v1.GameTelemetryService/TelemetryStream"
        )
        previous = None
        for frame in stream(b""):
            # TelemetryStreamResponse.actor.vitals.health
            health = frame
            for number in (6, 1, 1):
                health = field(health, number, 2)
                if health is None:
                    break
            if health is None:
                continue
            values = tuple(
                struct.unpack("<f", field(health, number, 5) or bytes(4))[0]
                for number in (1, 2)
            )
            if values != previous:
                print(f"Health: {values[0]:g}/{values[1]:g}", flush=True)
                previous = values


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except grpc.FutureTimeoutError:
        raise SystemExit("Could not connect to 127.0.0.1:2942. Check telemetry setup.")
    except grpc.RpcError as error:
        raise SystemExit(f"Telemetry stream failed: {error.details()}")
