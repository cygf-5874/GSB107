"""netcidr —— IP 区间代数（IPv4 / IPv6），仅用 Python 3 标准库。

本文件只给出类型与公开签名：`parse` / `union` / `to_cidrs` / `contains` /
`contains_range` / `difference` 的方法体一律 `raise NotImplementedError`，
需要按 README「对外契约」实现。

约束：地址的**文本解析**可以用 `ipaddress.ip_address`，但**区间代数**
（合并、差集、最少前缀分解）必须自己写，不许用 `ipaddress` 的
`collapse_addresses` / `summarize_address_range` / `supernet`。
"""

from __future__ import annotations

from typing import List, Optional


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
    raise NotImplementedError


def union(items: List[str]) -> RangeSet:
    """合并一组 CIDR 文本，返回规范形式的 `RangeSet`。"""
    raise NotImplementedError


def to_cidrs(rs: RangeSet) -> List[str]:
    """用**最少条数**、按 ``lo`` 升序的 CIDR 列表覆盖 ``rs``。"""
    raise NotImplementedError


def contains(rs: RangeSet, x: int) -> bool:
    """``x``（整数地址）是否落在 ``rs`` 里。"""
    raise NotImplementedError


def contains_range(rs: RangeSet, cidr: str) -> bool:
    """整个 CIDR 是否被 ``rs`` 包含。"""
    raise NotImplementedError


def difference(a: RangeSet, b: RangeSet) -> RangeSet:
    """区间差集 ``a \\ b``，返回规范形式的 `RangeSet`。"""
    raise NotImplementedError
