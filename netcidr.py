"""netcidr —— IP 区间代数（IPv4 / IPv6），仅用 Python 3 标准库。

公开 API 为 `parse` / `union` / `to_cidrs` / `contains` /
`contains_range` / `difference`，按 README「对外契约」实现。

约束：地址的**文本解析**可以用 `ipaddress.ip_address`，但**区间代数**
（合并、差集、最少前缀分解）必须自己写，不许用 `ipaddress` 的
`collapse_addresses` / `summarize_address_range` / `supernet`。
"""

from __future__ import annotations

import ipaddress
from typing import List, Optional

from errors import ErrBadCidr, ErrMixedFamily


def _address_width(family: int) -> int:
    if family == 4:
        return 32
    if family == 6:
        return 128
    raise ErrBadCidr("unknown IP address family: %r" % (family,))


def _merge_ranges(ranges: List[Range], family: int) -> List[Range]:
    ordered = sorted(ranges, key=lambda item: (item.lo, item.hi))
    merged: List[Range] = []
    for item in ordered:
        if not merged or item.lo > merged[-1].hi:
            merged.append(Range(item.lo, item.hi, family))
        elif item.hi > merged[-1].hi:
            merged[-1].hi = item.hi
    return merged


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
    if not isinstance(cidr, str):
        raise ErrBadCidr("CIDR must be a string")

    parts = cidr.split("/")
    if len(parts) != 2:
        raise ErrBadCidr("invalid CIDR: %r" % (cidr,))

    address_text, prefix_text = parts
    if not prefix_text or not all(char in "0123456789" for char in prefix_text):
        raise ErrBadCidr("invalid prefix length: %r" % (cidr,))

    try:
        address = ipaddress.ip_address(address_text)
    except (TypeError, ValueError) as exc:
        raise ErrBadCidr("invalid IP address: %r" % (cidr,)) from exc

    prefix_length = int(prefix_text)
    width = _address_width(address.version)
    if prefix_length < 0 or prefix_length > width:
        raise ErrBadCidr("prefix length out of range: %r" % (cidr,))

    block_size = 1 << (width - prefix_length)
    value = int(address)
    lo = (value // block_size) * block_size
    return Range(lo, lo + block_size, address.version)


def union(items: List[str]) -> RangeSet:
    """合并一组 CIDR 文本，返回规范形式的 `RangeSet`。"""
    ranges: List[Range] = []
    family: Optional[int] = None

    for text in items:
        parsed = parse(text)
        if family is None:
            family = parsed.family
        elif family != parsed.family:
            raise ErrMixedFamily(
                "cannot mix IPv%d and IPv%d" % (family, parsed.family)
            )
        ranges.append(parsed)

    if family is None:
        return RangeSet([], None)
    return RangeSet(_merge_ranges(ranges, family), family)


def to_cidrs(rs: RangeSet) -> List[str]:
    """用**最少条数**、按 ``lo`` 升序的 CIDR 列表覆盖 ``rs``。"""
    cidrs: List[str] = []

    for item in rs.ranges:
        family = rs.family if rs.family is not None else item.family
        width = _address_width(family)
        address_type = (
            ipaddress.IPv4Address if family == 4 else ipaddress.IPv6Address
        )
        space_size = 1 << width
        lo = item.lo

        while lo < item.hi:
            remaining = item.hi - lo
            largest_fitting = 1 << (remaining.bit_length() - 1)
            alignment = space_size if lo == 0 else lo & -lo
            block_size = min(largest_fitting, alignment)
            prefix_length = width - (block_size.bit_length() - 1)
            cidrs.append("%s/%d" % (address_type(lo), prefix_length))
            lo += block_size

    return cidrs


def contains(rs: RangeSet, x: int) -> bool:
    """``x``（整数地址）是否落在 ``rs`` 里。"""
    left = 0
    right = len(rs.ranges)

    while left < right:
        middle = (left + right) // 2
        if rs.ranges[middle].lo <= x:
            left = middle + 1
        else:
            right = middle

    index = left - 1
    return index >= 0 and x < rs.ranges[index].hi


def contains_range(rs: RangeSet, cidr: str) -> bool:
    """整个 CIDR 是否被 ``rs`` 包含。"""
    target = parse(cidr)
    if not rs.ranges or (
        rs.family is not None and rs.family != target.family
    ):
        return False

    left = 0
    right = len(rs.ranges)
    while left < right:
        middle = (left + right) // 2
        if rs.ranges[middle].lo <= target.lo:
            left = middle + 1
        else:
            right = middle

    index = left - 1
    return index >= 0 and target.hi <= rs.ranges[index].hi


def difference(a: RangeSet, b: RangeSet) -> RangeSet:
    """区间差集 ``a \\ b``，返回规范形式的 `RangeSet`。"""
    if (
        a.family is not None
        and b.family is not None
        and a.family != b.family
    ):
        raise ErrMixedFamily(
            "cannot subtract IPv%d from IPv%d" % (b.family, a.family)
        )

    result: List[Range] = []
    family = a.family
    removals = b.ranges
    removal_index = 0

    for source in a.ranges:
        if family is None:
            family = source.family

        lo = source.lo
        hi = source.hi

        while (
            removal_index < len(removals)
            and removals[removal_index].hi <= lo
        ):
            removal_index += 1

        scan_index = removal_index
        while scan_index < len(removals) and removals[scan_index].lo < hi:
            removal = removals[scan_index]
            if removal.lo > lo:
                result.append(Range(lo, removal.lo, family))
            if removal.hi > lo:
                lo = removal.hi
            if lo >= hi:
                break
            scan_index += 1

        if lo < hi:
            result.append(Range(lo, hi, family))

        while (
            removal_index < len(removals)
            and removals[removal_index].hi <= hi
        ):
            removal_index += 1

    return RangeSet(result, family)
