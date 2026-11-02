# -*- coding: utf-8 -*-
"""网络混沌代理：透明 TCP 代理，注入延迟/抖动/随机中断，模拟现场混乱网络。

- 多实例监听 127.0.0.1 的不同端口：每个端口对浏览器是独立 origin（存储/配额/会话隔离），
  终端按端口分组即获得 origin 级多样性。
  （macOS 无 sudo 无法给 lo0 加 127.0.0.x 别名，做不到真·多源 IP——应用侧统一见到 127.0.0.1，
  IP 多样性以「多 origin + 多端口连接」近似，已如实记录。）
- 每连接：随机预延迟 + 每块随机抖动延迟 + 按百分比随机中途断流（模拟弱网/丢包重连）。
- SSE 透明透传（延迟后仍流式）；断流触发浏览器 EventSource 自动重连——正是要考验的路径。

用法：
    from net_chaos import start_chaos_proxy
    stats = {"conns": 0, "aborted": 0, "errors": 0}
    servers = await start_chaos_proxy(ips, port, target_port, delay_max_ms=500,
                                      abort_pct=3.0, stats=stats)
    ...
    for s in servers: s.close()
"""
import asyncio
import random

IP_BLOCK = ["127.0.0.%d" % i for i in range(2, 40)]   # loopback /8 可用源 IP 池


class ChaosStats:
    def __init__(self):
        self.conns = 0
        self.aborted = 0
        self.errors = 0
        self.bytes_up = 0
        self.bytes_down = 0


async def _pump(reader, writer, base_delay, jitter, abort_evt: asyncio.Event):
    """把 reader 的数据块延迟后写入 writer；abort_evt 置位时随机掐断。"""
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                return
            delay = base_delay / 1000.0 + random.uniform(0, jitter) / 1000.0
            if delay > 0:
                await asyncio.sleep(delay)
            if abort_evt.is_set():
                return
            writer.write(chunk)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _handle(reader, writer, target_port, base_delay, jitter, abort_pct, stats):
    stats.conns += 1
    peer = writer.get_extra_info("peername")
    src_ip = peer[0] if peer else "127.0.0.1"
    # 回源轮换 loopback 源 IP，让应用服务器看到不同客户端地址
    abort_evt = asyncio.Event()
    try:
        remote_reader, remote_writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", target_port), timeout=5)
    except Exception:
        stats.errors += 1
        try:
            writer.close()
        except Exception:
            pass
        return
    # 随机中途断流：连接建立后 0.5~8s 内以 abort_pct 概率掐断（弱网/信号差）
    if random.uniform(0, 100) < abort_pct:
        stats.aborted += 1
        async def _abort_later():
            await asyncio.sleep(random.uniform(0.5, 8.0))
            abort_evt.set()
            try:
                remote_writer.close()
            except Exception:
                pass
            try:
                writer.close()
            except Exception:
                pass
        asyncio.ensure_future(_abort_later())
    up = _pump(reader, remote_writer, base_delay, jitter, abort_evt)
    down = _pump(remote_reader, writer, base_delay, jitter, abort_evt)
    await asyncio.gather(up, down, return_exceptions=True)


async def start_chaos_proxy(ports, target_port=None, *, delay_max_ms=300, abort_pct=2.0, stats=None):
    """在 127.0.0.1 的每个 port 上各起一个混沌代理实例，回源 127.0.0.1:target_port。"""
    stats = stats or ChaosStats()
    base = delay_max_ms * 0.4          # 每连接基础延迟 = 上限的 40%
    jitter = delay_max_ms * 0.6        # 每块随机抖动
    servers = []
    for port in ports:
        srv = await asyncio.start_server(
            lambda r, w: _handle(r, w, target_port or 8302, base, jitter, abort_pct, stats),
            host="127.0.0.1", port=port)
        servers.append(srv)
    return servers, stats
