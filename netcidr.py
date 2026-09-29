"""netcidr —— IP 区间代数（IPv4 / IPv6），仅用 Python 3 标准库。

公开 API：`parse` / `union` / `to_cidrs` / `contains` /
`contains_range` / `difference`，按 README「对外契约」实现。

约束：地址的**文本解析**可以用 `ipaddress.ip_address`，但**区间代数**
（合并、差集、最少前缀分解）必须自己写，不许用 `ipaddress` 的
`collapse_addresses` / `summarize_address_range` / `supernet`。
"""

from __future__ import annotations

import bisect
from ipaddress import ip_address
from typing import List, Optional, Tuple

from errors import ErrBadCidr, ErrMixedFamily


_FAMILY_MAXLEN = {4: 32, 6: 128}


class Range:
    """一个半开区间 ``[lo, hi)`` 的整数表示；``family`` 取 4（IPv4）或 6（IPv6）。"""

    __slots__ = ("lo", "hi", "family")

    def __init__(self, lo: int, hi: int, family: int) -> None:
        self.lo = lo
        self.hi = hi
        self.family = family

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Range):
            return NotImplemented
        return (self.lo, self.hi, self.family) == (other.lo, other.hi, other.family)

    def __hash__(self) -> int:
        return hash((self.lo, self.hi, self.family))

    def __repr__(self) -> str:
        return "Range(lo=%d, hi=%d, family=%d)" % (self.lo, self.hi, self.family)


class RangeSet:
    """地址区间的集合，内部表示**已定**：

    - ``ranges`` 是一组**互不相交**、按 ``lo`` **升序**的 `Range`；
    - ``family`` 是全集的地址族（空集合允许为 ``None``）。
    """

    __slots__ = ("ranges", "family")

    def __init__(self, ranges: Optional[List[Range]] = None,
                 family: Optional[int] = None) -> None:
        self.ranges: List[Range] = list(ranges) if ranges is not None else []
        self.family: Optional[int] = family


def parse(cidr: str) -> Range:
    """把 ``a.b.c.d/len`` 或 IPv6 的 ``addr/len`` 解析成半开区间 `Range`。

    非法输入抛 `ErrBadCidr`。
    """
    try:
        if not isinstance(cidr, str):
            raise ErrBadCidr("CIDR 必须是字符串: %r" % (cidr,))
        addr_text, sep, plen_text = cidr.partition("/")
        if not sep:
            raise ErrBadCidr("缺少 '/' 前缀: %r" % (cidr,))
        if not plen_text or any(ch not in "0123456789" for ch in plen_text):
            raise ErrBadCidr("前缀长度非法: %r" % (cidr,))
        addr = ip_address(addr_text)
        maxlen = _FAMILY_MAXLEN[addr.version]
        plen = int(plen_text)
        if plen < 0 or plen > maxlen:
            raise ErrBadCidr("前缀长度越界: %r" % (cidr,))
        shift = maxlen - plen
        lo = (int(addr) >> shift) << shift
        hi = lo + (1 << shift)
        return Range(lo, hi, addr.version)
    except ErrBadCidr:
        raise
    except Exception as exc:
        raise ErrBadCidr("无法解析 CIDR %r: %s" % (cidr, exc))


def _normalize(pairs: List[Tuple[int, int]], family: int) -> List[Range]:
    """按 lo 排序并合并所有重叠 / 相邻的半开区间（只做区间合并不做超网聚合）。"""
    ordered = sorted(pairs, key=lambda pair: pair[0])
    merged: List[Range] = []
    for lo, hi in ordered:
        if merged and lo <= merged[-1].hi:
            if hi > merged[-1].hi:
                merged[-1].hi = hi
        else:
            merged.append(Range(lo, hi, family))
    return merged


def union(items: List[str]) -> RangeSet:
    """合并一组 CIDR 文本，返回规范形式的 `RangeSet`。"""
    parsed = [parse(item) for item in items]
    family: Optional[int] = None
    for rng in parsed:
        if family is None:
            family = rng.family
        elif family != rng.family:
            raise ErrMixedFamily(
                "混用地址族: IPv%d 与 IPv%d" % (family, rng.family)
            )
    if family is None:
        return RangeSet([], None)
    return RangeSet(
        _normalize([(r.lo, r.hi) for r in parsed], family), family
    )


def to_cidrs(rs: RangeSet) -> List[str]:
    """用**最少条数**、按 ``lo`` 升序的 CIDR 列表覆盖 ``rs``。"""
    if not rs.ranges:
        return []
    maxlen = _FAMILY_MAXLEN[rs.family]
    space_size = 1 << maxlen
    result: List[str] = []
    for rng in rs.ranges:
        pos = rng.lo
        while pos < rng.hi:
            # 起点对齐度决定本块最大可取多大；/0 时 pos == 0 可覆盖整个空间。
            alignment = space_size if pos == 0 else (pos & -pos)
            size_limit = min(alignment, rng.hi - pos)
            block_bits = size_limit.bit_length() - 1
            size = 1 << block_bits
            prefix = maxlen - block_bits
            result.append("%s/%d" % (str(ip_address(pos)), prefix))
            pos += size
    return result


def contains(rs: RangeSet, x: int) -> bool:
    """``x``（整数地址）是否落在 ``rs`` 里。"""
    lows = [rng.lo for rng in rs.ranges]
    idx = bisect.bisect_right(lows, x) - 1
    if idx < 0:
        return False
    return rs.ranges[idx].hi > x


def contains_range(rs: RangeSet, cidr: str) -> bool:
    """整个 CIDR 是否被 ``rs`` 包含。"""
    rng = parse(cidr)
    if rs.family is not None and rs.family != rng.family:
        raise ErrMixedFamily(
            "混用地址族: RangeSet 为 IPv%d，CIDR 为 IPv%d"
            % (rs.family, rng.family)
        )
    lows = [r.lo for r in rs.ranges]
    idx = bisect.bisect_right(lows, rng.lo) - 1
    if idx < 0:
        return False
    holder = rs.ranges[idx]
    return holder.lo <= rng.lo and holder.hi >= rng.hi


def difference(a: RangeSet, b: RangeSet) -> RangeSet:
    """区间差集 ``a \\ b``，返回规范形式的 `RangeSet`。"""
    if a.family is not None and b.family is not None and a.family != b.family:
        raise ErrMixedFamily(
            "混用地址族: IPv%d 与 IPv%d" % (a.family, b.family)
        )
    result: List[Range] = []
    b_lows = [rng.lo for rng in b.ranges]
    b_highs = [rng.hi for rng in b.ranges]
    for part in a.ranges:
        # b 的 lo、hi 都严格升序，取所有与 part 可能相交的下标区间。
        k = bisect.bisect_right(b_highs, part.lo)
        end = bisect.bisect_left(b_lows, part.hi)
        cursor = part.lo
        while k < end:
            other = b.ranges[k]
            if other.hi > cursor:
                cut_lo = max(other.lo, part.lo)
                if cut_lo > cursor:
                    result.append(Range(cursor, cut_lo, part.family))
                cursor = other.hi
            k += 1
        if cursor < part.hi:
            result.append(Range(cursor, part.hi, part.family))
    return RangeSet(result, a.family)
