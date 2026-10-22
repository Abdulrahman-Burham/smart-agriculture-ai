"""Telemetry Service: Real-Time Hardware & Operating System Metrics Collector.

Measures CPU percentage, core counts, load averages, RAM & Swap utilization,
disk storage, process RSS memory, network interface RX/TX traffic, and server uptime.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import time
from typing import Any, Dict, Optional, Tuple

from app.core.config import DATA_DIR
from app.services.llm_service import get_gemini_key_pool_and_model

_APP_START_TS: float = time.time()
_LAST_CPU_SNAP: Optional[Tuple[int, int]] = None


def format_uptime_ar(seconds: float) -> str:
    """Format seconds into an Arabic human-readable string (e.g. '3 يوم • 5 ساعة • 12 دقيقة')."""
    secs = max(0, int(seconds))
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} يوم")
    if hours > 0 or days > 0:
        parts.append(f"{hours} ساعة")
    parts.append(f"{mins} دقيقة")
    return " • ".join(parts)


def _read_proc_cpu_times() -> Optional[Tuple[int, int]]:
    """Read Linux /proc/stat for instantaneous CPU idle and total ticks."""
    try:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            first = f.readline()
        if not first.startswith("cpu "):
            return None
        nums = [int(x) for x in first.split()[1:]]
        idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
        total = sum(nums)
        return (idle, total)
    except Exception:
        return None


def collect_server_system_metrics() -> Dict[str, Any]:
    """Collect real-time CPU, RAM, Swap, Disk, Network RX/TX, and Uptime metrics."""
    global _LAST_CPU_SNAP

    # 1. CPU Usage, Model & Load Average
    cpu_cores = os.cpu_count() or 1
    cpu_model = platform.processor() or "x86_64 vCPU"
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":", 1)[1].strip()
                        break
    except Exception:
        pass

    load_1m, load_5m, load_15m = 0.0, 0.0, 0.0
    try:
        if hasattr(os, "getloadavg"):
            l1, l5, l15 = os.getloadavg()
            load_1m, load_5m, load_15m = round(l1, 2), round(l5, 2), round(l15, 2)
    except Exception:
        pass

    cpu_pct = 0.0
    snap1 = _LAST_CPU_SNAP
    snap2 = _read_proc_cpu_times()
    if snap2:
        if snap1 is None or snap2[1] <= snap1[1]:
            time.sleep(0.06)
            snap1 = snap2
            snap2 = _read_proc_cpu_times() or snap1
        d_idle = snap2[0] - snap1[0]
        d_total = snap2[1] - snap1[1]
        if d_total > 0:
            cpu_pct = round(max(0.0, min(100.0, (1.0 - (d_idle / d_total)) * 100.0)), 1)
        _LAST_CPU_SNAP = snap2
    elif load_1m > 0:
        cpu_pct = round(min(100.0, (load_1m / max(1, cpu_cores)) * 100.0), 1)

    # 2. RAM, Swap & Process RSS Memory
    ram_total_gb, ram_used_gb, ram_avail_gb, ram_pct = 0.0, 0.0, 0.0, 0.0
    swap_total_gb, swap_used_gb, swap_pct = 0.0, 0.0, 0.0
    app_rss_mb = 0.0
    try:
        if os.path.exists("/proc/meminfo"):
            mem_map: Dict[str, int] = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        parts = v.strip().split()
                        if parts and parts[0].isdigit():
                            mem_map[k.strip()] = int(parts[0])
            tot_kb = mem_map.get("MemTotal", 0)
            avail_kb = mem_map.get(
                "MemAvailable",
                mem_map.get("MemFree", 0)
                + mem_map.get("Buffers", 0)
                + mem_map.get("Cached", 0),
            )
            used_kb = max(0, tot_kb - avail_kb)
            if tot_kb > 0:
                ram_total_gb = round(tot_kb / (1024 * 1024), 2)
                ram_used_gb = round(used_kb / (1024 * 1024), 2)
                ram_avail_gb = round(avail_kb / (1024 * 1024), 2)
                ram_pct = round((used_kb * 100.0) / tot_kb, 1)
            sw_tot = mem_map.get("SwapTotal", 0)
            sw_free = mem_map.get("SwapFree", 0)
            sw_used = max(0, sw_tot - sw_free)
            if sw_tot > 0:
                swap_total_gb = round(sw_tot / (1024 * 1024), 2)
                swap_used_gb = round(sw_used / (1024 * 1024), 2)
                swap_pct = round((sw_used * 100.0) / sw_tot, 1)
    except Exception:
        pass

    try:
        if os.path.exists("/proc/self/status"):
            with open("/proc/self/status", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split()[1])
                        app_rss_mb = round(rss_kb / 1024.0, 1)
                        break
    except Exception:
        pass

    # 3. Disk Usage
    disk_total_gb, disk_used_gb, disk_free_gb, disk_pct = 0.0, 0.0, 0.0, 0.0
    try:
        du = shutil.disk_usage("/")
        disk_total_gb = round(du.total / (1024**3), 2)
        disk_used_gb = round(du.used / (1024**3), 2)
        disk_free_gb = round(du.free / (1024**3), 2)
        disk_pct = round((du.used * 100.0) / du.total, 1) if du.total > 0 else 0.0
    except Exception:
        pass

    db_file = DATA_DIR / "predictions_history.db"
    db_size_mb = (
        round(db_file.stat().st_size / (1024 * 1024), 2) if db_file.exists() else 0.0
    )

    # 4. Network Interface RX / TX Traffic
    net_rx_mb, net_tx_mb, net_rx_gb, net_tx_gb = 0.0, 0.0, 0.0, 0.0
    net_rx_packets, net_tx_packets = 0, 0
    try:
        if os.path.exists("/proc/net/dev"):
            rx_bytes, tx_bytes = 0, 0
            with open("/proc/net/dev", "r", encoding="utf-8") as f:
                for line in f:
                    if ":" not in line:
                        continue
                    iface, stats_str = line.split(":", 1)
                    if iface.strip() == "lo":
                        continue
                    fields = stats_str.split()
                    if len(fields) >= 10:
                        rx_bytes += int(fields[0])
                        net_rx_packets += int(fields[1])
                        tx_bytes += int(fields[8])
                        net_tx_packets += int(fields[9])
            net_rx_mb = round(rx_bytes / (1024 * 1024), 1)
            net_tx_mb = round(tx_bytes / (1024 * 1024), 1)
            net_rx_gb = round(rx_bytes / (1024**3), 2)
            net_tx_gb = round(tx_bytes / (1024**3), 2)
    except Exception:
        pass

    # 5. Server & Service Uptime
    server_uptime_sec = time.time() - _APP_START_TS
    try:
        if os.path.exists("/proc/uptime"):
            with open("/proc/uptime", "r", encoding="utf-8") as f:
                server_uptime_sec = float(f.read().split()[0])
    except Exception:
        pass
    app_uptime_sec = time.time() - _APP_START_TS

    keys, primary_gemini_model = get_gemini_key_pool_and_model()

    return {
        "cpu": {
            "usage_pct": cpu_pct,
            "cores": cpu_cores,
            "model": cpu_model,
            "load_1m": load_1m,
            "load_5m": load_5m,
            "load_15m": load_15m,
        },
        "memory": {
            "total_gb": ram_total_gb,
            "used_gb": ram_used_gb,
            "available_gb": ram_avail_gb,
            "usage_pct": ram_pct,
            "swap_total_gb": swap_total_gb,
            "swap_used_gb": swap_used_gb,
            "swap_pct": swap_pct,
            "app_rss_mb": app_rss_mb,
        },
        "disk": {
            "total_gb": disk_total_gb,
            "used_gb": disk_used_gb,
            "free_gb": disk_free_gb,
            "usage_pct": disk_pct,
            "db_size_mb": db_size_mb,
        },
        "network": {
            "rx_mb": net_rx_mb,
            "tx_mb": net_tx_mb,
            "rx_gb": net_rx_gb,
            "tx_gb": net_tx_gb,
            "rx_packets": net_rx_packets,
            "tx_packets": net_tx_packets,
        },
        "system": {
            "hostname": socket.gethostname(),
            "os_info": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "python_version": platform.python_version(),
            "server_uptime": format_uptime_ar(server_uptime_sec),
            "app_uptime": format_uptime_ar(app_uptime_sec),
            "cv_loaded": True,
            "gemini_keys_count": len(keys),
            "gemini_model": primary_gemini_model,
        },
    }
