import socket, time, importlib.metadata
print("--- Raw Python socket: TCP+SSH banner per VM ---")
for host in ["10.1.0.184", "10.1.0.185", "10.1.0.186"]:
    t0 = time.time()
    try:
        s = socket.socket()
        s.settimeout(10)
        s.connect((host, 22))
        b = s.recv(256)
        s.close()
        print(f"  {host}: OK ({time.time()-t0:.2f}s) banner={b.decode(errors='replace').strip()[:70]}")
    except Exception as e:
        print(f"  {host}: FAIL ({time.time()-t0:.2f}s) {type(e).__name__}: {e}")
print()
try:
    print(f"paramiko version: {importlib.metadata.version('paramiko')}")
except Exception as e:
    print(f"paramiko version: ERROR {e}")
try:
    print(f"cryptography version: {importlib.metadata.version('cryptography')}")
except Exception as e:
    print(f"cryptography version: ERROR {e}")
print()
print("--- Paramiko single-VM with 30s timeout + verbose phases (dev only) ---")
import paramiko, logging
logging.basicConfig(level=logging.WARNING)
t0 = time.time()
try:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname="10.1.0.184", username="erpadmin", password="dummy-just-test-banner",
              timeout=30, banner_timeout=30, auth_timeout=15,
              allow_agent=False, look_for_keys=False)
    print(f"  unexpected success in {time.time()-t0:.2f}s")
    c.close()
except paramiko.AuthenticationException as e:
    print(f"  AUTH-FAIL after {time.time()-t0:.2f}s (good - means SSH handshake worked, password is just wrong)")
except Exception as e:
    print(f"  FAIL after {time.time()-t0:.2f}s {type(e).__name__}: {e}")