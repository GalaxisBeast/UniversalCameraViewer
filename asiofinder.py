import sounddevice as sd

print("Host APIs:")
for i, hostapi in enumerate(sd.query_hostapis()):
    print(f"{i}: {hostapi['name']}")

asio_hostapi_index = None
for i, hostapi in enumerate(sd.query_hostapis()):
    if hostapi['name'].lower() == 'asio':
        asio_hostapi_index = i
        break

if asio_hostapi_index is None:
    print("No ASIO host API found on this system.")
else:
    print(f"ASIO host API found at index {asio_hostapi_index}")
    print("Devices supporting ASIO:")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['hostapi'] == asio_hostapi_index:
            print(f"  {i}: {dev['name']}")
