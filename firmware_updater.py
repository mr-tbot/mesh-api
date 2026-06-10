"""
firmware_updater.py — Firmware & software update manager for MESH-API v0.7.0.

Provides a comprehensive, *safe-by-default* update system:

  * **Detection** — identifies the connected Meshtastic device (hardware model +
    firmware variant ``pioEnv`` + current firmware version) and the connected
    MeshCore device (model + firmware version).
  * **Update checks** — queries GitHub releases for the latest Meshtastic
    firmware, MeshCore firmware, and MESH-API itself, and reports whether a
    newer version is available for each. Runs on demand and (optionally) on a
    periodic background timer. Results are cached for the web UI to show a
    notification banner.
  * **Flashing** — for ESP32-class Meshtastic devices on a serial port it can
    download the correct firmware asset and flash it via ``esptool`` (OFF by
    default; gated behind ``firmware.allow_flashing`` and an explicit request).
    For nRF52/UF2 devices and MeshCore companions — where unattended flashing is
    unsafe/impossible without putting the device into bootloader mode — it
    returns clear, guided instructions and a web-flasher link instead.

Safety
------
Flashing can brick a radio, so:
  * ``firmware.allow_flashing`` defaults to **false** (master gate),
  * ``firmware.auto_update`` defaults to **false** (never flashes unattended),
  * a flash requires the caller to stop the radio interface first (the core
    passes ``stop_interface``/``start_interface`` callbacks),
  * only recognised ESP32 variants are auto-flashed; everything else returns
    guidance.

This module has no hard dependency on ``esptool``; if flashing is requested but
``esptool`` is missing it degrades to guidance.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from typing import Any, Callable, Optional
from urllib.request import Request, urlopen

MESH_API_VERSION = "0.7.3"

# Default upstream GitHub repos (configurable via the ``firmware`` config block).
DEFAULT_MESHTASTIC_FW_REPO = "meshtastic/firmware"
DEFAULT_MESHCORE_FW_REPO = "meshcore-dev/MeshCore"
DEFAULT_MESHAPI_REPO = "mr-tbot/mesh-api"

# ESP32 family markers (these can be flashed over serial with esptool).
_ESP32_MARKERS = ("esp32", "esp32s3", "esp32-s3", "esp32c3", "esp32-c3", "tbeam",
                  "heltec", "tlora", "station-g", "wireless-paper", "wireless-tracker")
# nRF52 / RAK / T-Echo use UF2 drag-and-drop and cannot be safely auto-flashed.
_NRF_MARKERS = ("nrf52", "rak4631", "rak", "t-echo", "techo", "canaryone", "wio-tracker")


def _norm_version(v: Optional[str]) -> str:
    """Reduce a version string to comparable dotted numerals (e.g.
    '2.7.15.567b8ea' -> '2.7.15', 'v0.7.0 Beta' -> '0.7.0')."""
    if not v:
        return ""
    m = re.search(r"(\d+(?:\.\d+){1,3})", str(v))
    return m.group(1) if m else ""


def _version_tuple(v: str) -> tuple:
    parts = _norm_version(v).split(".") if _norm_version(v) else []
    out = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            out.append(0)
    while len(out) < 4:
        out.append(0)
    return tuple(out[:4])


def is_newer(latest: str, current: str) -> bool:
    """True if ``latest`` is a strictly newer version than ``current``."""
    nl, nc = _norm_version(latest), _norm_version(current)
    if not nl or not nc:
        return False
    return _version_tuple(nl) > _version_tuple(nc)


class FirmwareUpdater:
    def __init__(
        self,
        config: dict,
        providers: dict,
        log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._cfg = config or {}
        self._providers = providers or {}
        self._log = log or (lambda m: print(m))
        self._lock = threading.Lock()
        self._cache: dict = {
            "checked_at": None,
            "mesh_api": {"current": MESH_API_VERSION, "latest": None, "update_available": False, "url": None},
            "meshtastic": {"device": None, "current": None, "latest": None, "update_available": False, "url": None},
            "meshcore": {"device": None, "current": None, "latest": None, "update_available": False, "url": None},
        }
        self._flash_state: dict = {"active": False, "progress": "", "result": None}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── config helpers ───────────────────────────────────────────────

    def _c(self, key: str, default: Any = None) -> Any:
        return self._cfg.get(key, default)

    @property
    def auto_check(self) -> bool:
        return bool(self._c("auto_check", True))

    @property
    def allow_flashing(self) -> bool:
        return bool(self._c("allow_flashing", False))

    @property
    def auto_update(self) -> bool:
        return bool(self._c("auto_update", False))

    # ── lifecycle ────────────────────────────────────────────────────

    def start(self) -> None:
        if not self.auto_check:
            self._log("[Firmware] periodic update checks disabled.")
            return
        self._thread = threading.Thread(target=self._loop, name="firmware-checker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        # Initial delay so radios are connected first.
        self._interruptible_sleep(int(self._c("startup_delay_sec", 45)))
        interval = max(3600, int(self._c("check_interval_sec", 86400)))
        while not self._stop.is_set():
            try:
                self.check_updates()
                if self.auto_update and self.allow_flashing:
                    self._maybe_auto_update()
            except Exception as exc:
                self._log(f"[Firmware] periodic check error: {exc}")
            self._interruptible_sleep(interval)

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end and not self._stop.is_set():
            time.sleep(1)

    # ── GitHub helpers ───────────────────────────────────────────────

    def _gh_latest_release(self, repo: str) -> Optional[dict]:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            req = Request(url, headers={"Accept": "application/vnd.github+json",
                                        "User-Agent": "mesh-api-updater"})
            with urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except Exception as exc:
            self._log(f"[Firmware] could not fetch latest release for {repo}: {exc}")
            return None

    def _gh_list_releases(self, repo: str) -> list:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=30"
        try:
            req = Request(url, headers={"Accept": "application/vnd.github+json",
                                        "User-Agent": "mesh-api-updater"})
            with urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
                return data if isinstance(data, list) else []
        except Exception as exc:
            self._log(f"[Firmware] could not list releases for {repo}: {exc}")
            return []

    def _pick_release(self, repo: str, channel: str) -> Optional[dict]:
        """Pick a GitHub release for the requested channel.

        channel: 'stable' (newest non-prerelease), 'beta' (newest prerelease,
        preferring tags/names containing 'beta'), or 'alpha' (newest prerelease,
        preferring 'alpha'). Falls back to stable when a channel has no matching
        release.
        """
        channel = (channel or "stable").lower()
        if channel == "stable":
            rel = self._gh_latest_release(repo)
            if rel:
                return rel
            releases = self._gh_list_releases(repo)
            for r in releases:
                if not r.get("draft") and not r.get("prerelease"):
                    return r
            return releases[0] if releases else None

        releases = self._gh_list_releases(repo)
        if not releases:
            return self._gh_latest_release(repo)
        pres = [r for r in releases if r.get("prerelease") and not r.get("draft")]
        # Prefer a prerelease whose tag/name mentions the channel word.
        for r in pres:
            label = f"{r.get('tag_name','')} {r.get('name','')}".lower()
            if channel in label:
                return r
        if pres:
            return pres[0]  # newest prerelease
        # No prereleases at all -> fall back to stable.
        for r in releases:
            if not r.get("draft") and not r.get("prerelease"):
                return r
        return releases[0]

    # ── detection ────────────────────────────────────────────────────

    def detect_meshtastic(self) -> dict:
        getter = self._providers.get("get_meshtastic_device_info")
        info = (getter() if getter else {}) or {}
        return {
            "hw_model": info.get("hw_model"),
            "pio_env": info.get("pio_env"),
            "firmware_version": _norm_version(info.get("firmware_version")),
            "firmware_raw": info.get("firmware_version"),
            "port": info.get("port"),
        }

    def detect_meshcore(self) -> dict:
        getter = self._providers.get("get_meshcore_device_info")
        info = (getter() if getter else {}) or {}
        return {
            "model": info.get("model"),
            "firmware_version": _norm_version(info.get("firmware_version")),
            "firmware_raw": info.get("firmware_version"),
        }

    # ── update checks ────────────────────────────────────────────────

    def check_updates(self) -> dict:
        with self._lock:
            self._check_mesh_api()
            self._check_meshtastic()
            self._check_meshcore()
            self._cache["checked_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            return json.loads(json.dumps(self._cache))  # deep copy

    def _check_mesh_api(self) -> None:
        repo = self._c("mesh_api_repo", DEFAULT_MESHAPI_REPO)
        rel = self._gh_latest_release(repo)
        entry = self._cache["mesh_api"]
        entry["current"] = MESH_API_VERSION
        if rel:
            tag = rel.get("tag_name") or rel.get("name")
            entry["latest"] = tag
            entry["url"] = rel.get("html_url")
            entry["update_available"] = is_newer(tag, MESH_API_VERSION)

    def _check_meshtastic(self) -> None:
        dev = self.detect_meshtastic()
        entry = self._cache["meshtastic"]
        entry["device"] = dev
        entry["current"] = dev.get("firmware_version")
        channel = self._c("meshtastic_channel", "stable")
        entry["channel"] = channel
        if not entry["current"]:
            entry["update_available"] = False
            return
        repo = self._c("meshtastic_fw_repo", DEFAULT_MESHTASTIC_FW_REPO)
        rel = self._pick_release(repo, channel)
        if rel:
            tag = rel.get("tag_name") or rel.get("name")
            entry["latest"] = tag
            entry["url"] = rel.get("html_url")
            entry["prerelease"] = bool(rel.get("prerelease"))
            entry["update_available"] = is_newer(tag, entry["current"])
            entry["_release"] = {"tag": tag, "assets": [
                {"name": a.get("name"), "url": a.get("browser_download_url")}
                for a in rel.get("assets", [])
            ]}

    def _check_meshcore(self) -> None:
        dev = self.detect_meshcore()
        entry = self._cache["meshcore"]
        entry["device"] = dev
        entry["current"] = dev.get("firmware_version")
        channel = self._c("meshcore_channel", "stable")
        entry["channel"] = channel
        repo = self._c("meshcore_fw_repo", DEFAULT_MESHCORE_FW_REPO)
        rel = self._pick_release(repo, channel)
        if rel:
            tag = rel.get("tag_name") or rel.get("name")
            entry["latest"] = tag
            entry["url"] = rel.get("html_url")
            entry["prerelease"] = bool(rel.get("prerelease"))
            entry["update_available"] = bool(entry["current"]) and is_newer(tag, entry["current"])
        else:
            entry["latest"] = None
            entry["update_available"] = False

    def get_status(self) -> dict:
        with self._lock:
            data = json.loads(json.dumps(self._cache))
        # strip the bulky release asset list from the public status
        data["meshtastic"].pop("_release", None)
        data["flashing"] = dict(self._flash_state)
        data["allow_flashing"] = self.allow_flashing
        data["auto_update"] = self.auto_update
        data["auto_check"] = self.auto_check
        data["channels"] = {
            "meshtastic": self._c("meshtastic_channel", "stable"),
            "meshcore": self._c("meshcore_channel", "stable"),
        }
        n = sum(1 for k in ("mesh_api", "meshtastic", "meshcore")
                if data.get(k, {}).get("update_available"))
        data["updates_available"] = n
        return data

    def set_channel(self, which: str, channel: str) -> dict:
        """Set the release channel for 'meshtastic' or 'meshcore' firmware to
        one of stable/beta/alpha, then re-check. Persists via save_config if
        the core provided one."""
        channel = (channel or "stable").lower()
        if channel not in ("stable", "beta", "alpha"):
            return {"ok": False, "error": "channel must be stable, beta, or alpha"}
        if which == "meshtastic":
            self._cfg["meshtastic_channel"] = channel
        elif which == "meshcore":
            self._cfg["meshcore_channel"] = channel
        else:
            return {"ok": False, "error": "which must be meshtastic or meshcore"}
        save = self._providers.get("save_config")
        if save:
            try:
                save()
            except Exception:
                pass
        self.check_updates()
        return {"ok": True, "status": self.get_status()}

    # ── flashing (ESP32 Meshtastic only; gated) ──────────────────────

    def _esp_variant(self, pio_env: Optional[str], hw_model: Optional[str]) -> bool:
        s = f"{pio_env or ''} {hw_model or ''}".lower()
        if any(m in s for m in _NRF_MARKERS):
            return False
        return any(m in s for m in _ESP32_MARKERS)

    def flash_meshtastic(self, request_confirm: bool = False) -> dict:
        """Attempt to flash the latest Meshtastic firmware to an ESP32 device.

        Returns a dict describing the outcome or the guidance to follow. Does
        nothing destructive unless flashing is allowed, the device is an ESP32
        variant, and ``request_confirm`` is True.
        """
        with self._lock:
            entry = self._cache.get("meshtastic", {})
            dev = entry.get("device") or self.detect_meshtastic()
            rel = entry.get("_release")
            latest = entry.get("latest")

        pio_env = dev.get("pio_env")
        hw_model = dev.get("hw_model")
        port = dev.get("port") or self._c("meshtastic_serial_port")

        if not self.allow_flashing:
            return {"ok": False, "guidance": True,
                    "message": "Firmware flashing is disabled. Set firmware.allow_flashing=true to enable, "
                               "or use the Meshtastic web flasher.",
                    "web_flasher": "https://flasher.meshtastic.org/"}

        if not self._esp_variant(pio_env, hw_model):
            return {"ok": False, "guidance": True,
                    "message": f"Device '{hw_model or pio_env}' is not an auto-flashable ESP32 variant "
                               "(e.g. nRF52/UF2 devices flash by drag-and-drop). Use the web flasher.",
                    "web_flasher": "https://flasher.meshtastic.org/"}

        if not request_confirm:
            return {"ok": False, "confirm_required": True,
                    "message": f"Confirm flashing Meshtastic firmware {latest} to {hw_model} on {port}. "
                               "The radio will be offline during flashing. Re-call with confirm=true."}

        if not port:
            return {"ok": False, "message": "No Meshtastic serial port known; cannot flash."}

        # Find the matching '-update.bin' asset for this pioEnv.
        asset_url = self._pick_update_asset(rel, pio_env)
        if not asset_url:
            return {"ok": False, "guidance": True,
                    "message": f"Could not find an update firmware asset for variant '{pio_env}' in the "
                               f"latest release. Use the web flasher.",
                    "web_flasher": "https://flasher.meshtastic.org/"}

        return self._do_esp_flash(port, asset_url, latest)

    def _pick_update_asset(self, rel: Optional[dict], pio_env: Optional[str]) -> Optional[str]:
        if not rel or not pio_env:
            return None
        assets = rel.get("assets", [])
        # Prefer a per-variant '-update.bin'; some releases ship a big zip.
        for a in assets:
            name = (a.get("name") or "").lower()
            if pio_env.lower() in name and name.endswith("update.bin"):
                return a.get("url")
        for a in assets:
            name = (a.get("name") or "").lower()
            if name.startswith("firmware-") and name.endswith(".zip"):
                return a.get("url")  # zip: handled by _do_esp_flash (extract)
        return None

    def _do_esp_flash(self, port: str, asset_url: str, version: Optional[str]) -> dict:
        if self._flash_state["active"]:
            return {"ok": False, "message": "A flash is already in progress."}
        try:
            import esptool  # noqa: F401
        except Exception:
            return {"ok": False, "guidance": True,
                    "message": "esptool is not installed (pip install esptool). Use the web flasher.",
                    "web_flasher": "https://flasher.meshtastic.org/"}

        self._flash_state = {"active": True, "progress": "starting", "result": None}
        try:
            stop_iface = self._providers.get("stop_interface")
            start_iface = self._providers.get("start_interface")
            tmpdir = tempfile.mkdtemp(prefix="meshfw_")
            self._flash_state["progress"] = "downloading firmware"
            local = os.path.join(tmpdir, "fw_download")
            self._download(asset_url, local)

            bin_path = local
            if asset_url.lower().endswith(".zip") or zipfile.is_zipfile(local):
                self._flash_state["progress"] = "extracting"
                bin_path = self._extract_update_bin(local, tmpdir)
                if not bin_path:
                    raise RuntimeError("no -update.bin found in firmware zip")

            # Release the serial port before flashing.
            if stop_iface:
                self._flash_state["progress"] = "stopping radio interface"
                try:
                    stop_iface()
                    time.sleep(2)
                except Exception:
                    pass

            self._flash_state["progress"] = f"flashing {version} (do not unplug)"
            self._log(f"[Firmware] flashing {version} to {port} from {os.path.basename(bin_path)}")
            cmd = [sys.executable, "-m", "esptool", "--port", port, "--baud", "115200",
                   "write_flash", "0x10000", bin_path]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            ok = proc.returncode == 0
            tail = (proc.stdout or "")[-800:] + "\n" + (proc.stderr or "")[-400:]
            self._flash_state["result"] = {"ok": ok, "log": tail}
            self._log(f"[Firmware] flash {'succeeded' if ok else 'FAILED'} (rc={proc.returncode})")

            if start_iface:
                self._flash_state["progress"] = "restarting radio interface"
                try:
                    start_iface()
                except Exception:
                    pass
            return {"ok": ok, "version": version, "log": tail}
        except Exception as exc:
            self._flash_state["result"] = {"ok": False, "error": str(exc)}
            self._log(f"[Firmware] flash error: {exc}")
            return {"ok": False, "message": f"Flash error: {exc}"}
        finally:
            self._flash_state["active"] = False

    def _download(self, url: str, dest: str) -> None:
        req = Request(url, headers={"User-Agent": "mesh-api-updater",
                                    "Accept": "application/octet-stream"})
        with urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)

    def _extract_update_bin(self, zip_path: str, outdir: str) -> Optional[str]:
        try:
            with zipfile.ZipFile(zip_path) as z:
                names = z.namelist()
                cand = [n for n in names if n.lower().endswith("update.bin")]
                if not cand:
                    cand = [n for n in names if n.lower().endswith(".bin")]
                if not cand:
                    return None
                target = cand[0]
                z.extract(target, outdir)
                return os.path.join(outdir, target)
        except Exception:
            return None

    def _maybe_auto_update(self) -> None:
        """Called by the periodic loop when auto_update + allow_flashing are on.
        Conservatively only flashes ESP32 Meshtastic devices."""
        mt = self._cache.get("meshtastic", {})
        if mt.get("update_available"):
            self._log("[Firmware] auto-update: Meshtastic firmware update available; flashing.")
            self.flash_meshtastic(request_confirm=True)
