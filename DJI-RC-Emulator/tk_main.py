"""
Ultra-Low-Latency 2-Thread Tkinter GUI for DJI RC Pro Enterprise Simulator Controller.
- Automatically kills any duplicate Python RC processes on startup so only 1 Xbox 360 Controller exists.
- Uses a dedicated USB Reader Thread + Paced Writer Thread so USB FIFO lag is strictly 0 ms.
- Applies smooth exponential curve (Expo) to the Gimbal wheel and removes unwanted Y/B/DPad button punches.
"""
import os
import sys
import time
import subprocess
import logging
from threading import Thread, Event
import tkinter as tk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

logging.basicConfig(
    filename=os.path.join(APP_DIR, "emulator.log"),
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("tk_main")


_last_com_reclaim_time = 0.0


def kill_other_instances():
    """Close any OTHER running copy of this emulator (tk_main.py, main.py, or DJI RC Emulator.exe)
    so only one holds the DJI USB/COM interface and one virtual Xbox pad exists."""
    my_pid = os.getpid()
    try:
        cmd = (
            'powershell -NoProfile -Command "'
            "Stop-Process -Name 'DJI RC Emulator' -Force -ErrorAction SilentlyContinue; "
            "Get-CimInstance Win32_Process -Filter \\\"Name like 'python%'\\\" | "
            "Where-Object { ($_.CommandLine -match 'tk_main\\.py|main\\.py') -and $_.ProcessId -ne " + str(my_pid) + " } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }\""
        )
        subprocess.run(cmd, shell=True, timeout=6, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.3)
    except Exception as e:
        logger.debug("kill_other_instances: %s", e)


def reclaim_locked_com_port(com_port: str) -> serial.Serial | None:
    """
    When DJI Virtual Flight (DFSM-Win64-Shipping.exe) or an old process grabs COM3 before the
    emulator, restart the DJI USB VCOM PnP device while polling serial.Serial(com_port) every 2ms
    so our emulator snatches the exclusive COM handle first.
    """
    global _last_com_reclaim_time
    now = time.time()
    if now - _last_com_reclaim_time < 18.0:
        return None
    _last_com_reclaim_time = now

    my_pid = os.getpid()
    ps_script = (
        f"Stop-Process -Name 'DJI RC Emulator' -Force -ErrorAction SilentlyContinue; "
        f"Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
        f"Where-Object {{ ($_.CommandLine -match 'tk_main\\.py|main\\.py') -and $_.ProcessId -ne {my_pid} }} | "
        f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}; "
        f"Get-PnpDevice -Class Ports -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.FriendlyName -match '{com_port}' -or $_.InstanceId -match 'VID_2CA3|VID_FFF0' }} | "
        f"ForEach-Object {{ pnputil /restart-device \"$($_.InstanceId)\" | Out-Null }}"
    )

    def _trigger_reset():
        try:
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_admin = False
        try:
            if is_admin:
                subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                    timeout=10,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                elev_cmd = (
                    "Start-Process powershell -WindowStyle Hidden -Verb RunAs "
                    f"-ArgumentList '-NoProfile -ExecutionPolicy Bypass -Command \"{ps_script}\"'"
                )
                subprocess.run(["powershell", "-NoProfile", "-Command", elev_cmd], timeout=10)
        except Exception as e:
            logger.debug("reclaim_locked_com_port reset error: %s", e)

    Thread(target=_trigger_reset, daemon=True, name="COMReclaim").start()

    deadline = time.perf_counter() + 6.5
    while time.perf_counter() < deadline:
        try:
            return serial.Serial(port=com_port, baudrate=115200, timeout=0.015, write_timeout=0.5)
        except Exception:
            time.sleep(0.002)
    return None


from src.config_manager import ConfigManager
from src.duml import (
    build_enable_simulator,
    build_read_sticks,
    extract_all_packets_from_bytes,
    parse_stick_data,
)
from src.usb_transport import USBBulkTransport, load_custom_pids
from src.rc_connection import find_dji_port
from src.input_processor import InputProcessor, apply_deadzone, apply_expo
from src.gamepad import VirtualGamepad, VGAMEPAD_AVAILABLE
from src.auto_driver import extract_drivers_to_disk
import serial

try:
    extract_drivers_to_disk()
except Exception:
    pass


class StickCanvas(tk.Canvas):
    """2D visual crosshair widget for a joystick."""
    def __init__(self, parent, title: str, size: int = 190):
        super().__init__(parent, width=size, height=size + 28, bg="#181825", highlightthickness=1, highlightbackground="#313244")
        self.size = size
        self.pad = 16
        self.cx = size // 2
        self.cy = (size // 2) + 18
        self.radius = (size // 2) - self.pad

        self.create_text(self.cx, 12, text=title, fill="#cdd6f4", font=("Segoe UI", 9, "bold"))
        self.create_rectangle(
            self.cx - self.radius, self.cy - self.radius,
            self.cx + self.radius, self.cy + self.radius,
            outline="#45475a", width=1, fill="#11111b"
        )
        self.create_line(self.cx - self.radius, self.cy, self.cx + self.radius, self.cy, fill="#313244", dash=(2, 2))
        self.create_line(self.cx, self.cy - self.radius, self.cx, self.cy + self.radius, fill="#313244", dash=(2, 2))
        r = 7
        self.dot = self.create_oval(self.cx - r, self.cy - r, self.cx + r, self.cy + r, fill="#89b4fa", outline="#b4befe", width=2)
        self.val_text = self.create_text(self.cx, size + 18, text="X: +0.00  Y: +0.00", fill="#a6adc8", font=("Consolas", 9))

    def update_pos(self, x_int: int, y_int: int):
        nx = max(-1.0, min(1.0, x_int / 32767.0))
        ny = max(-1.0, min(1.0, y_int / 32767.0))
        px = self.cx + nx * self.radius
        py = self.cy - ny * self.radius
        r = 7
        self.coords(self.dot, px - r, py - r, px + r, py + r)
        self.itemconfigure(self.val_text, text=f"X: {nx:+.2f}  Y: {ny:+.2f}")


class DialBar(tk.Canvas):
    """Horizontal bar for Gimbal and Scroll wheels."""
    def __init__(self, parent, width: int = 180, height: int = 18):
        super().__init__(parent, width=width, height=height, bg="#11111b", highlightthickness=1, highlightbackground="#45475a")
        self.w = width
        self.h = height
        self.cx = width // 2
        self.create_line(self.cx, 0, self.cx, height, fill="#585b70", width=1)
        self.bar = self.create_rectangle(self.cx, 2, self.cx, height - 2, fill="#89b4fa", outline="")

    def update_val(self, norm_val: float):
        v = max(-1.0, min(1.0, norm_val))
        px = self.cx + int(v * (self.w // 2 - 2))
        x0, x1 = (self.cx, px) if px >= self.cx else (px, self.cx)
        self.coords(self.bar, x0, 2, x1, self.h - 2)


class DualThreadRCReader:
    """
    Two-thread USB architecture:
      - Reader thread continuously drains EP_IN (5,000+ pkt/s capacity) so the OS/RC USB
        buffer is ALWAYS empty (0 ms queue delay).
      - Writer thread sends read_sticks requests at a paced 125 Hz (every 8ms) and wakes
        immediately when the reader thread receives a fresh stick packet.
    """
    def __init__(self):
        self._usb: USBBulkTransport | None = None
        self._serial: serial.Serial | None = None
        self._stop = Event()
        self._stick_event = Event()
        self._latest_stick: dict | None = None
        self._last_rx_time = 0.0
        self._main_thread: Thread | None = None
        self.connected = False
        self.port_name = ""
        self.packets_per_sec = 0.0
        # True = emulator releases the COM/USB port so the simulator drives the controller natively (FPV mode)
        self.native_fpv_mode = False

        self.on_stick_data = None
        self.on_connection_changed = None
        self.on_error = None

    def start(self):
        if self._main_thread and self._main_thread.is_alive():
            return
        self._stop.clear()
        self._main_thread = Thread(target=self._supervisor_loop, daemon=True, name="RCSupervisor")
        self._main_thread.start()

    def stop(self):
        self._stop.set()
        self._stick_event.set()
        if self._main_thread:
            self._main_thread.join(timeout=2.0)
            self._main_thread = None
        self._close()

    def _close(self):
        if self._usb:
            try:
                self._usb.close()
            except Exception:
                pass
            self._usb = None
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        if self.connected:
            self.connected = False
            self.port_name = ""
            self.packets_per_sec = 0.0
            if self.on_connection_changed:
                self.on_connection_changed(False, "")

    def _supervisor_loop(self):
        while not self._stop.is_set():
            if self.native_fpv_mode:
                self._close()
                self._stop.wait(0.3)
                continue
            serial_err = None
            try:
                # 1. Try Serial COM port if present (used by DJI RC-N1 / Air 2S controller on bottom USB-C port)
                com_port = find_dji_port()
                if com_port:
                    try:
                        self._serial = serial.Serial(port=com_port, baudrate=115200, timeout=0.015, write_timeout=0.5)
                    except Exception as e:
                        err_str = str(e)
                        if "PermissionError" in err_str or "Acesso negado" in err_str or "Access is denied" in err_str:
                            if self.on_error:
                                self.on_error(f"Liberando porta {com_port} automaticamente...")
                            self._serial = reclaim_locked_com_port(com_port)
                        if self._serial is None:
                            serial_err = e

                if self._serial is not None:
                    self._serial.write(build_enable_simulator())
                    time.sleep(0.05)
                    self._serial.reset_input_buffer()

                    self.connected = True
                    self.port_name = f"Serial:{com_port} (RC-N1 / Air 2S)"
                    self._last_rx_time = time.perf_counter()
                    if self.on_connection_changed:
                        self.on_connection_changed(True, self.port_name)

                    conn_stop = Event()
                    reader = Thread(target=self._continuous_serial_reader, args=(conn_stop,), daemon=True, name="SerialReader")
                    reader.start()
                    self._paced_serial_writer(conn_stop)
                    conn_stop.set()
                    reader.join(timeout=1.0)
                else:
                    # 2. Try USB Bulk (DJI RC Pro Enterprise, DJI RC, RC 2, RC-N1/N2/N3 via WinUSB)
                    try:
                        self._usb = USBBulkTransport()
                        self._usb.open()
                    except Exception as usb_exc:
                        if serial_err is not None:
                            s_msg = str(serial_err)
                            if "PermissionError" in s_msg or "Acesso negado" in s_msg or "Access is denied" in s_msg:
                                raise ConnectionError(
                                    f"Porta {com_port} presa pelo DJI Virtual Flight! Feche o simulador, espere ficar VERDE aqui e abra o simulador depois."
                                ) from serial_err
                            raise serial_err
                        raise usb_exc

                    self._usb.write(build_enable_simulator())
                    time.sleep(0.05)

                    # Flush startup packets
                    while True:
                        d = self._usb.read(512, timeout=5)
                        if not d:
                            break

                    self.connected = True
                    self.port_name = self._usb.port
                    self._last_rx_time = time.perf_counter()
                    if self.on_connection_changed:
                        self.on_connection_changed(True, self.port_name)

                    conn_stop = Event()
                    reader = Thread(target=self._continuous_reader, args=(conn_stop,), daemon=True, name="USBReader")
                    reader.start()

                    self._paced_writer(conn_stop)
                    conn_stop.set()
                    reader.join(timeout=1.0)

            except Exception as e:
                if self.on_error:
                    self.on_error(str(e))
            finally:
                self._close()

            if not self._stop.is_set():
                self._stop.wait(1.5)

    def _continuous_serial_reader(self, conn_stop: Event):
        """Dedicated thread that drains Serial IN bytes for DJI RC-N1 (Air 2S)."""
        pkt_count = 0
        stat_t0 = time.perf_counter()
        buf = bytearray()

        while not self._stop.is_set() and not conn_stop.is_set():
            try:
                chunk = self._serial.read(256)
                if not chunk:
                    continue
                buf.extend(chunk)
                packets = extract_all_packets_from_bytes(bytes(buf))
                if packets:
                    buf.clear()
                    latest = None
                    for pkt in packets:
                        parsed = parse_stick_data(pkt)
                        if parsed is not None:
                            latest = parsed
                    if latest is not None:
                        self._latest_stick = latest
                        self._last_rx_time = time.perf_counter()
                        self._stick_event.set()
                        pkt_count += 1
                elif len(buf) > 1024:
                    buf = buf[-256:]

                now = time.perf_counter()
                dt = now - stat_t0
                if dt >= 1.0:
                    self.packets_per_sec = pkt_count / dt
                    pkt_count = 0
                    stat_t0 = now
            except Exception as e:
                logger.error("Serial reader error: %s", e)
                conn_stop.set()
                break

    def _paced_serial_writer(self, conn_stop: Event):
        while not self._stop.is_set() and not conn_stop.is_set() and not self.native_fpv_mode:
            now = time.perf_counter()
            if (now - self._last_rx_time) > 2.5:
                raise ConnectionError("Conexão Serial com controle DJI perdida")
            self._serial.write(build_read_sticks())
            if self._stick_event.wait(timeout=0.008):
                self._stick_event.clear()
                data = self._latest_stick
                if data is not None and self.on_stick_data:
                    self.on_stick_data(data)
            time.sleep(0.005)

    def _continuous_reader(self, conn_stop: Event):
        """Dedicated thread that drains USB IN packets non-stop."""
        pkt_count = 0
        stat_t0 = time.perf_counter()

        while not self._stop.is_set() and not conn_stop.is_set():
            try:
                raw = self._usb.read(512, timeout=15)
                if not raw:
                    continue
                packets = extract_all_packets_from_bytes(raw)
                latest = None
                for pkt in packets:
                    parsed = parse_stick_data(pkt)
                    if parsed is not None:
                        latest = parsed

                if latest is not None:
                    self._latest_stick = latest
                    self._last_rx_time = time.perf_counter()
                    self._stick_event.set()
                    pkt_count += 1

                now = time.perf_counter()
                dt = now - stat_t0
                if dt >= 1.0:
                    self.packets_per_sec = pkt_count / dt
                    pkt_count = 0
                    stat_t0 = now
            except Exception as e:
                logger.error("Reader thread error: %s", e)
                conn_stop.set()
                break

    def _paced_writer(self, conn_stop: Event):
        """Paced writer thread: sends read_sticks at ~140 Hz and pushes newest stick data."""
        while not self._stop.is_set() and not conn_stop.is_set() and not self.native_fpv_mode:
            now = time.perf_counter()
            if (now - self._last_rx_time) > 2.5:
                raise ConnectionError("Conexão USB com controle DJI perdida")

            # Send read_sticks request
            self._usb.write(build_read_sticks())

            # Wait up to 7ms for reader thread to flag fresh data
            if self._stick_event.wait(timeout=0.007):
                self._stick_event.clear()
                data = self._latest_stick
                if data is not None and self.on_stick_data:
                    self.on_stick_data(data)

            # Small pacing sleep so we never flood the RC's internal DUML CPU
            time.sleep(0.005)


class TkApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DJI RC Pro Enterprise — Simulador (Zero-Delay + Gimbal Suave)")
        self.root.geometry("740x540")
        self.root.configure(bg="#1e1e2e")
        self.root.resizable(False, False)

        self.config_mgr = ConfigManager()
        self.config = self.config_mgr.load()
        custom_pids = self.config.get("custom_usb_pids", [])
        if custom_pids:
            load_custom_pids(custom_pids)

        self.input_proc = InputProcessor()
        self.input_proc.load_from_config(self.config)

        self.gamepad = VirtualGamepad()
        self.gamepad.load_from_config(self.config)
        # IMPORTANT: Remove Y/B/DPad button mappings from camera/scroll wheels by default
        # so the gimbal wheel does NOT fire button "punches/jerks" when tilted!
        # Gimbal wheel -> D-Pad Up/Down (held while the wheel is turned) in 'dpad' mode.
        self.gamepad.button_map["camera_up"] = ""
        self.gamepad.button_map["camera_down"] = ""
        self.gamepad.button_map["scroll_up"] = "DPad Up"
        self.gamepad.button_map["scroll_down"] = "DPad Down"

        self.rc = DualThreadRCReader()
        self._latest_processed = None
        self._gimbal_held_pos = 0.0  # -1.0 .. +1.0 for held-angle mode
        self._last_stick_time = time.perf_counter()

        self._build_ui()

        self.rc.on_stick_data = self._on_stick_data
        self.rc.on_connection_changed = self._on_connection_changed
        self.rc.on_error = self._on_error
        self.gamepad.on_error = self._on_error

        if not VGAMEPAD_AVAILABLE:
            self.lbl_gamepad.config(text="Gamepad: ERRO (Instale ViGEmBus)", fg="#f38ba8")
        elif self.gamepad.initialize():
            self.lbl_gamepad.config(text="Gamepad Virtual: Xbox 360 Controller #1 [ZERO DELAY ATIVO]", fg="#a6e3a1")
        else:
            self.lbl_gamepad.config(text="Gamepad Virtual: Falha ao iniciar ViGEmBus", fg="#f38ba8")

        self.rc.native_fpv_mode = self.sim_mode.get() == "fpv"
        self._toggle_connect()
        if self.rc.native_fpv_mode:
            self._on_sim_mode_change()

        self.root.after(16, self._ui_tick)
        self.root.after(1000, self._stats_tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        top = tk.Frame(self.root, bg="#181825", padx=16, pady=10)
        top.pack(fill=tk.X)

        self.lbl_status = tk.Label(
            top, text="● Conectando ao controle DJI...", fg="#f9e2af", bg="#181825",
            font=("Segoe UI", 11, "bold")
        )
        self.lbl_status.pack(side=tk.LEFT)

        self.btn_connect = tk.Button(
            top, text="Desconectar", bg="#45475a", fg="#cdd6f4", activebackground="#585b70",
            activeforeground="#ffffff", relief=tk.FLAT, padx=14, pady=3,
            font=("Segoe UI", 9, "bold"), command=self._toggle_connect
        )
        self.btn_connect.pack(side=tk.RIGHT)

        sub = tk.Frame(self.root, bg="#1e1e2e", padx=16, pady=4)
        sub.pack(fill=tk.X)
        self.lbl_gamepad = tk.Label(
            sub, text="Gamepad Virtual: Inicializando...", fg="#89b4fa", bg="#1e1e2e",
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_gamepad.pack(side=tk.LEFT)

        self.lbl_rate = tk.Label(
            sub, text="Taxa USB: 0 Hz", fg="#a6e3a1", bg="#1e1e2e",
            font=("Consolas", 10, "bold")
        )
        self.lbl_rate.pack(side=tk.RIGHT)

        # Gimbal mode selector bar
        mode_bar = tk.Frame(self.root, bg="#181825", padx=12, pady=6)
        mode_bar.pack(fill=tk.X, padx=16, pady=(2, 4))
        tk.Label(
            mode_bar, text="Modo Gimbal:", fg="#cdd6f4", bg="#181825",
            font=("Segoe UI", 9, "bold")
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.gimbal_mode = tk.StringVar(value="dpad")
        modes = [
            ("D-Pad Cima/Baixo (segura)", "dpad"),
            ("Gatilhos LT/RT suaves", "split_triggers"),
            ("Segurar Ângulo (LT)", "held_lt"),
            ("Eixo Direto LT", "single_lt"),
        ]
        for text, val in modes:
            rb = tk.Radiobutton(
                mode_bar, text=text, variable=self.gimbal_mode, value=val,
                bg="#181825", fg="#cdd6f4", selectcolor="#313244",
                activebackground="#181825", activeforeground="#89b4fa",
                font=("Segoe UI", 8)
            )
            rb.pack(side=tk.LEFT, padx=4)

        # Simulator mode selector: normal drone (virtual Xbox pad) vs native FPV controller
        sim_bar = tk.Frame(self.root, bg="#181825", padx=12, pady=6)
        sim_bar.pack(fill=tk.X, padx=16, pady=(0, 4))
        tk.Label(
            sim_bar, text="Modo do Simulador:", fg="#cdd6f4", bg="#181825",
            font=("Segoe UI", 9, "bold")
        ).pack(side=tk.LEFT, padx=(0, 6))
        self.sim_mode = tk.StringVar(value=self.config.get("sim_mode", "normal"))
        for text, val in [
            ("Drone Normal (Xbox 360 virtual)", "normal"),
            ("FPV nativo (libera a COM pro simulador)", "fpv"),
        ]:
            tk.Radiobutton(
                sim_bar, text=text, variable=self.sim_mode, value=val,
                command=self._on_sim_mode_change,
                bg="#181825", fg="#cdd6f4", selectcolor="#313244",
                activebackground="#181825", activeforeground="#89b4fa",
                font=("Segoe UI", 8)
            ).pack(side=tk.LEFT, padx=4)

        # Main sticks area
        sticks_frame = tk.Frame(self.root, bg="#1e1e2e", padx=12, pady=4)
        sticks_frame.pack(fill=tk.BOTH, expand=True)

        self.left_stick = StickCanvas(sticks_frame, "Stick Esquerdo (Throttle / Yaw)", size=190)
        self.left_stick.pack(side=tk.LEFT, padx=10)

        mid = tk.Frame(sticks_frame, bg="#1e1e2e")
        mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)

        tk.Label(mid, text="Rodinha do Gimbal (Entrada)", fg="#cdd6f4", bg="#1e1e2e", font=("Segoe UI", 9, "bold")).pack(pady=(6, 2))
        self.cam_bar = DialBar(mid, width=180, height=16)
        self.cam_bar.pack()
        self.lbl_cam = tk.Label(mid, text="0.00  (LT: 128 | RT: 0)", fg="#89b4fa", bg="#1e1e2e", font=("Consolas", 9, "bold"))
        self.lbl_cam.pack(pady=(2, 6))

        tk.Label(mid, text="Posição Atual do Gimbal", fg="#cdd6f4", bg="#1e1e2e", font=("Segoe UI", 9, "bold")).pack(pady=(4, 2))
        self.held_bar = DialBar(mid, width=180, height=16)
        self.held_bar.pack()
        self.lbl_scroll = tk.Label(mid, text="Ângulo: 0%", fg="#a6e3a1", bg="#1e1e2e", font=("Consolas", 9, "bold"))
        self.lbl_scroll.pack(pady=(2, 6))

        tk.Label(mid, text="Botões do Controle", fg="#cdd6f4", bg="#1e1e2e", font=("Segoe UI", 9, "bold")).pack(pady=(6, 4))
        btn_row = tk.Frame(mid, bg="#1e1e2e")
        btn_row.pack()
        self.btn_labels = {}
        for name, label in [("c1", "C1"), ("c2", "C2"), ("photo", "Foto"), ("video", "Vídeo"), ("fn", "Fn")]:
            lbl = tk.Label(btn_row, text=label, bg="#313244", fg="#6c7086", padx=6, pady=3, font=("Segoe UI", 8, "bold"))
            lbl.pack(side=tk.LEFT, padx=2)
            self.btn_labels[name] = lbl

        self.right_stick = StickCanvas(sticks_frame, "Stick Direito (Pitch / Roll)", size=190)
        self.right_stick.pack(side=tk.RIGHT, padx=10)

        self_footer = tk.Frame(self.root, bg="#181825", padx=16, pady=8)
        self_footer.pack(fill=tk.X, side=tk.BOTTOM)
        self.lbl_msg = tk.Label(
            self_footer,
            text="Instâncias antigas encerradas! Controle único sem conflito USB e gimbal suave sem socos.",
            fg="#a6e3a1", bg="#181825", font=("Segoe UI", 9)
        )
        self.lbl_msg.pack(side=tk.LEFT)

    def _on_sim_mode_change(self):
        fpv = self.sim_mode.get() == "fpv"
        self.rc.native_fpv_mode = fpv
        try:
            self.config_mgr.set("sim_mode", self.sim_mode.get())
            self.config_mgr.save()
        except Exception as e:
            logger.debug("save sim_mode: %s", e)
        if fpv:
            self.lbl_status.config(text="● Modo FPV nativo: porta liberada para o simulador", fg="#f9e2af")
            self.lbl_msg.config(
                text="O simulador controla o RC direto (como controle FPV). Sticks NAO passam pelo Xbox virtual.",
                fg="#f9e2af")
        else:
            self.lbl_status.config(text="● Procurando controle DJI via USB...", fg="#f9e2af")
            self.lbl_msg.config(
                text="Modo Drone Normal: espere ficar VERDE aqui e SO ENTAO abra o simulador.",
                fg="#a6e3a1")

    def _toggle_connect(self):
        if self.rc.connected or (self.rc._main_thread and self.rc._main_thread.is_alive()):
            self.rc.stop()
            self.lbl_status.config(text="● Desconectado", fg="#f38ba8")
            self.btn_connect.config(text="Conectar")
        else:
            self.lbl_status.config(text="● Procurando controle DJI via USB...", fg="#f9e2af")
            self.btn_connect.config(text="Desconectar")
            self.rc.start()

    def _on_stick_data(self, raw_data: dict):
        now = time.perf_counter()
        dt = max(0.001, min(0.05, now - self._last_stick_time))
        self._last_stick_time = now

        processed = self.input_proc.process(raw_data)

        # Never fire digital button punches from the gimbal wheel
        processed["camera_up"] = False
        processed["camera_down"] = False
        processed["scroll_up"] = False
        processed["scroll_down"] = False

        # Smooth exponential curve on the gimbal wheel so small movements are ultra-fine
        cam_raw = apply_deadzone(processed.get("camera", 0.0), 0.03)
        scr_raw = apply_deadzone(processed.get("scroll", 0.0), 0.03)
        cam_smooth = apply_expo(cam_raw, 0.55)
        scr_smooth = apply_expo(scr_raw, 0.55)
        active_dial = cam_smooth if abs(cam_smooth) >= abs(scr_smooth) else scr_smooth

        mode = self.gimbal_mode.get()
        processed["dial"] = active_dial
        if mode == "dpad":
            # Proportional PWM on D-Pad Up/Down + proportional LT/RT triggers:
            # Small wheel tilt -> gentle pulses for fine gimbal adjustment; full tilt -> continuous hold.
            processed["left_trigger"] = int(max(0.0, min(1.0, -active_dial)) * 255)
            processed["right_trigger"] = int(max(0.0, min(1.0, active_dial)) * 255)
            mag = abs(active_dial)
            if mag < 0.05:
                self._dpad_accum = 0.0
                fire = False
            elif mag >= 0.75:
                fire = True
            else:
                self._dpad_accum = getattr(self, "_dpad_accum", 0.0) + mag
                if self._dpad_accum >= 1.0:
                    self._dpad_accum -= 1.0
                    fire = True
                else:
                    fire = False
            processed["scroll_up"] = fire and (active_dial > 0)
            processed["scroll_down"] = fire and (active_dial < 0)
            self._gimbal_held_pos = active_dial
        elif mode == "held_lt":
            # Integrate wheel smoothly so you can nudge the gimbal up/down slightly and it stays!
            self._gimbal_held_pos = max(-1.0, min(1.0, self._gimbal_held_pos + active_dial * dt * 0.9))
            lt_val = int(((self._gimbal_held_pos + 1.0) * 0.5) * 255)
            processed["left_trigger"] = max(0, min(255, lt_val))
            processed["right_trigger"] = int(max(0.0, min(1.0, (active_dial + 1.0) * 0.5)) * 255) if abs(active_dial) > 0 else 0
        elif mode == "single_lt":
            self._gimbal_held_pos = active_dial
            processed["left_trigger"] = int(max(0.0, min(1.0, (active_dial + 1.0) * 0.5)) * 255)
            processed["right_trigger"] = int(max(0.0, min(1.0, (scr_smooth + 1.0) * 0.5)) * 255)
        else:
            # Smooth proportional LT (down) / RT (up) without any button jerks
            self._gimbal_held_pos = active_dial
            processed["left_trigger"] = int(max(0.0, min(1.0, -active_dial)) * 255)
            processed["right_trigger"] = int(max(0.0, min(1.0, active_dial)) * 255)

        if self.gamepad.is_initialized:
            self.gamepad.push(processed)
        self._latest_processed = processed

    def _on_connection_changed(self, connected: bool, port: str):
        def _upd():
            if connected:
                self.lbl_status.config(text=f"● Conectado: {port}", fg="#a6e3a1")
                self.btn_connect.config(text="Desconectar")
            elif self.rc.native_fpv_mode:
                self.lbl_status.config(text="● Modo FPV nativo: porta liberada para o simulador", fg="#f9e2af")
            else:
                self.lbl_status.config(text="● Desconectado", fg="#f38ba8")
                self.btn_connect.config(text="Conectar")
        self.root.after(0, _upd)

    def _on_error(self, message: str):
        def _upd():
            short = message.splitlines()[0] if message else "Erro"
            self.lbl_msg.config(text=f"Aviso: {short}", fg="#f38ba8")
        self.root.after(0, _upd)

    def _ui_tick(self):
        p = self._latest_processed
        if p is not None:
            self.left_stick.update_pos(p.get("gamepad_left_x", 0), p.get("gamepad_left_y", 0))
            self.right_stick.update_pos(p.get("gamepad_right_x", 0), p.get("gamepad_right_y", 0))
            cam = p.get("dial", 0.0)
            lt = p.get("left_trigger", 0)
            rt = p.get("right_trigger", 0)
            self.cam_bar.update_val(cam)
            self.held_bar.update_val(self._gimbal_held_pos)
            self.lbl_cam.config(text=f"{cam:+.2f}  (LT: {lt:3d} | RT: {rt:3d})")
            self.lbl_scroll.config(text=f"Ângulo: {self._gimbal_held_pos * 100:+.0f}%")
            for k, lbl in self.btn_labels.items():
                if p.get(k, False):
                    lbl.config(bg="#a6e3a1", fg="#11111b")
                else:
                    lbl.config(bg="#313244", fg="#6c7086")
        self.root.after(16, self._ui_tick)

    def _stats_tick(self):
        if self.rc.connected:
            self.lbl_rate.config(text=f"Taxa USB: {self.rc.packets_per_sec:.0f} Hz (Zero-Delay)")
        else:
            self.lbl_rate.config(text="Taxa USB: 0 Hz")
        self.root.after(1000, self._stats_tick)

    def _on_close(self):
        self.rc.stop()
        self.gamepad.stop()
        self.root.destroy()

    def run(self):
        self.root.deiconify()
        self.root.update_idletasks()
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(1500, lambda: self.root.attributes("-topmost", False))
        self.root.mainloop()


if __name__ == "__main__":
    try:
        kill_other_instances()
        TkApp().run()
    except Exception:
        logger.exception("Fatal error in TkApp")
        raise
