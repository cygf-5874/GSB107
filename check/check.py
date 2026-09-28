#!/usr/bin/env python3
"""netcidr 的固定验收程序。

场景（10 个）：parse 2 + union 2 + tocidrs 3 + diff 2 + family 1。

本文件属于固定判据，解题者不得修改。期望值全部是硬编码或由标准库
`ipaddress` 独立算出；判据不依赖墙钟、机器速度、`dict` 迭代顺序或随机源。
"""

import argparse
import ipaddress
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from errors import ErrBadCidr, ErrMixedFamily  # noqa: E402
from netcidr import (  # noqa: E402
    RangeSet,
    contains,
    contains_range,
    difference,
    parse,
    to_cidrs,
    union,
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _verdict(ok, expected, actual):
    return (bool(ok), expected, actual)


def _addr(text):
    return int(ipaddress.ip_address(text))


def _iv(rs):
    """把 RangeSet 的内部表示摊成 [(lo, hi, family), ...]。"""
    return [(r.lo, r.hi, r.family) for r in rs.ranges]


def _oracle_parse(cidr):
    net = ipaddress.ip_network(cidr, strict=False)
    return (int(net.network_address), int(net.broadcast_address) + 1, net.version)


def _address_count(rs):
    return sum(r.hi - r.lo for r in rs.ranges)


def _cidrs_address_count(cidrs):
    total = 0
    for text in cidrs:
        net = ipaddress.ip_network(text, strict=False)
        total += int(net.broadcast_address) - int(net.network_address) + 1
    return total


# --------------------------------------------------------------------------
# parse group
# --------------------------------------------------------------------------

_PARSE_OK = (
    "192.168.0.0/24",
    "10.1.2.3/32",
    "0.0.0.0/0",
    "8.8.8.8/29",
    "2001:db8::/32",
    "::1/128",
    "::/0",
    "2001:db8::1/128",
    "fe80::/10",
)


def scenario_parse_ipv4_ipv6():
    problems = []
    for text in _PARSE_OK:
        want = _oracle_parse(text)
        rng = parse(text)
        got = (rng.lo, rng.hi, rng.family)
        if got != want:
            problems.append("%s→%r(期望 %r)" % (text, got, want))
    ok = not problems
    return _verdict(ok, "全部区间正确", "通过" if ok else ";".join(problems))


_PARSE_BAD = (
    "",
    "1.2.3.4/33",
    "1.2.3.4/-1",
    "1.2.3.4/",
    "1.2.3.4/12x",
    "300.1.1.1/24",
    "::/129",
    "hello",
    "1.2.3.4/24/24",
)


def scenario_parse_reject_bad():
    problems = []
    for text in _PARSE_BAD:
        try:
            parse(text)
            problems.append("%r:未抛" % (text,))
        except ErrBadCidr:
            pass
        except NotImplementedError:
            raise
        except Exception as exc:  # noqa: BLE001
            problems.append("%r:%s" % (text, type(exc).__name__))
    ok = not problems
    return _verdict(ok, "全部抛 ErrBadCidr", "通过" if ok else ";".join(problems))


# --------------------------------------------------------------------------
# union group
# --------------------------------------------------------------------------

def scenario_union_overlapping():
    rs = union(["10.0.0.0/24", "10.0.0.128/25", "10.0.0.0/25"])
    want = [(_addr("10.0.0.0"), _addr("10.0.1.0"), 4)]
    problems = []
    if _iv(rs) != want:
        problems.append("区间=%r(期望 %r)" % (_iv(rs), want))
    checks = (
        ("contains 10.0.0.5", contains(rs, _addr("10.0.0.5")), True),
        ("contains 10.0.0.255", contains(rs, _addr("10.0.0.255")), True),
        ("contains 10.0.1.0(半开)", contains(rs, _addr("10.0.1.0")), False),
        ("contains_range 10.0.0.0/25", contains_range(rs, "10.0.0.0/25"), True),
        ("contains_range 10.0.0.0/24", contains_range(rs, "10.0.0.0/24"), True),
        ("contains_range 10.0.0.0/23", contains_range(rs, "10.0.0.0/23"), False),
    )
    for label, got, exp in checks:
        if bool(got) != exp:
            problems.append("%s=%r(期望 %r)" % (label, got, exp))
    ok = not problems
    return _verdict(ok, "重叠合并为 10.0.0.0/24", "通过" if ok else ";".join(problems))


def scenario_union_adjacent():
    problems = []
    cases = (
        (["10.0.0.0/25", "10.0.0.128/25"],
         [(_addr("10.0.0.0"), _addr("10.0.1.0"), 4)]),
        (["192.168.0.0/24", "192.168.1.0/24"],
         [(_addr("192.168.0.0"), _addr("192.168.2.0"), 4)]),
        (["10.0.0.0/24", "10.0.2.0/24"],
         [(_addr("10.0.0.0"), _addr("10.0.1.0"), 4),
          (_addr("10.0.2.0"), _addr("10.0.3.0"), 4)]),
        (["192.168.1.5/32", "192.168.1.5/32", "192.168.1.5/32"],
         [(_addr("192.168.1.5"), _addr("192.168.1.6"), 4)]),
    )
    for items, want in cases:
        got = _iv(union(items))
        if got != want:
            problems.append("%r→%r(期望 %r)" % (items, got, want))
    # 输入顺序倒过来，输出仍按 lo 升序
    got = _iv(union(["10.0.2.0/24", "10.0.0.0/24"]))
    want = [(_addr("10.0.0.0"), _addr("10.0.1.0"), 4),
            (_addr("10.0.2.0"), _addr("10.0.3.0"), 4)]
    if got != want:
        problems.append("倒序输入→%r(期望 %r)" % (got, want))
    ok = not problems
    return _verdict(ok, "相邻区间合并、结果升序", "通过" if ok else ";".join(problems))


# --------------------------------------------------------------------------
# tocidrs group
# --------------------------------------------------------------------------

_COVER_CASES = (
    (["10.0.0.0/24"], ["10.0.0.0/24"]),
    (["10.0.0.0/25", "10.0.0.128/26", "10.0.0.192/26"], ["10.0.0.0/24"]),
    (["0.0.0.0/0"], ["0.0.0.0/0"]),
    (["192.168.1.0/24", "192.168.0.0/25"],
     ["192.168.0.0/25", "192.168.1.0/24"]),
    (["2001:db8::/33", "2001:db8:8000::/33"], ["2001:db8::/32"]),
)


def scenario_tocidrs_cover_correctness():
    problems = []
    for items, want in _COVER_CASES:
        rs = union(items)
        got = to_cidrs(rs)
        if got != want:
            problems.append("%r→%r(期望 %r)" % (items, got, want))
            continue
        # 覆盖等价：把结果重新解析、地址总数必须与集合一致
        if _cidrs_address_count(got) != _address_count(rs):
            problems.append("%r:地址数不符 %d != %d"
                            % (items, _cidrs_address_count(got), _address_count(rs)))
    ok = not problems
    return _verdict(ok, "覆盖集合且与逐条解析一致", "通过" if ok else ";".join(problems))


_MIN_COUNT_CASES = (
    (["0.0.0.0/32", "0.0.0.1/32", "0.0.0.2/32", "0.0.0.3/32", "0.0.0.4/32"],
     ["0.0.0.0/30", "0.0.0.4/32"]),
    (["0.0.0.1/32", "0.0.0.2/32", "0.0.0.3/32", "0.0.0.4/32",
      "0.0.0.5/32", "0.0.0.6/32", "0.0.0.7/32"],
     ["0.0.0.1/32", "0.0.0.2/31", "0.0.0.4/30"]),
)


def scenario_tocidrs_minimal_count():
    problems = []
    for items, want in _MIN_COUNT_CASES:
        got = to_cidrs(union(items))
        if got != want:
            problems.append("%r→%r(期望 %r，共 %d 条)"
                            % (items, got, want, len(want)))
        elif len(got) != len(want):
            problems.append("%r:条数 %d != %d" % (items, len(got), len(want)))
    ok = not problems
    return _verdict(ok, "条数最少（非对齐边界不多拆）", "通过" if ok else ";".join(problems))


def scenario_tocidrs_ascending():
    problems = []
    got = to_cidrs(union(["192.168.10.0/24", "10.0.0.0/24", "172.16.0.0/24"]))
    want = ["10.0.0.0/24", "172.16.0.0/24", "192.168.10.0/24"]
    if got != want:
        problems.append("多区间→%r(期望 %r)" % (got, want))
    else:
        los = [int(ipaddress.ip_network(c).network_address) for c in got]
        if los != sorted(los) or len(set(los)) != len(los):
            problems.append("未严格升序: %r" % (los,))
    if to_cidrs(union([])) != []:
        problems.append("空集合 to_cidrs != []")
    if contains(union([]), 0) is not False:
        problems.append("空集合 contains != False")
    if contains(union([]), _addr("0.0.0.0")) is not False:
        problems.append("空集合 contains(0.0.0.0) != False")
    ok = not problems
    return _verdict(ok, "按 lo 升序 + 空集合边界", "通过" if ok else ";".join(problems))


# --------------------------------------------------------------------------
# diff group
# --------------------------------------------------------------------------

_DIFF_CASES = (
    (["10.0.0.0/24"], ["10.0.0.0/25"], ["10.0.0.128/25"]),
    (["10.0.0.0/24"], ["10.0.0.64/26"], ["10.0.0.0/26", "10.0.0.128/25"]),
    (["10.0.0.0/24"], ["10.0.0.0/24"], []),
    (["10.0.0.0/24"], ["192.168.0.0/24"], ["10.0.0.0/24"]),
    (["2001:db8::/32"], ["2001:db8:8000::/33"], ["2001:db8::/33"]),
)


def scenario_diff_correctness():
    problems = []
    for a_items, b_items, want in _DIFF_CASES:
        got = to_cidrs(difference(union(a_items), union(b_items)))
        if got != want:
            problems.append("%r \\ %r→%r(期望 %r)"
                            % (a_items, b_items, got, want))
    ok = not problems
    return _verdict(ok, "差集覆盖正确", "通过" if ok else ";".join(problems))


def scenario_diff_normalized():
    problems = []
    a = union(["10.0.0.0/25", "10.0.0.128/25"])
    b = union(["10.0.0.32/27"])
    d = difference(a, b)
    want_ranges = [(_addr("10.0.0.0"), _addr("10.0.0.32"), 4),
                   (_addr("10.0.0.64"), _addr("10.0.1.0"), 4)]
    if _iv(d) != want_ranges:
        problems.append("区间=%r(期望 %r)" % (_iv(d), want_ranges))
    if to_cidrs(d) != ["10.0.0.0/27", "10.0.0.64/26", "10.0.0.128/25"]:
        problems.append("to_cidrs=%r" % (to_cidrs(d),))
    if _iv(a) != [(_addr("10.0.0.0"), _addr("10.0.1.0"), 4)]:
        problems.append("入参 a 被改动: %r" % (_iv(a),))
    if _iv(b) != [(_addr("10.0.0.32"), _addr("10.0.0.64"), 4)]:
        problems.append("入参 b 被改动: %r" % (_iv(b),))
    ok = not problems
    return _verdict(ok, "结果规范化且不改入参", "通过" if ok else ";".join(problems))


# --------------------------------------------------------------------------
# family group
# --------------------------------------------------------------------------

def scenario_family_mixed_rejected():
    problems = []
    mixed_inputs = (
        ["10.0.0.0/24", "2001:db8::/32"],
        ["2001:db8::/32", "10.0.0.0/24"],
        ["2001:db8::/32", "::1/128", "10.0.0.0/8"],
    )
    for items in mixed_inputs:
        try:
            union(items)
            problems.append("union%r:未抛" % (items,))
        except ErrMixedFamily:
            pass
        except NotImplementedError:
            raise
        except Exception as exc:  # noqa: BLE001
            problems.append("union%r:%s" % (items, type(exc).__name__))
    try:
        difference(union(["10.0.0.0/24"]), union(["2001:db8::/32"]))
        problems.append("difference:未抛")
    except ErrMixedFamily:
        pass
    except NotImplementedError:
        raise
    except Exception as exc:  # noqa: BLE001
        problems.append("difference:%s" % (type(exc).__name__,))
    ok = not problems
    return _verdict(ok, "混用地址族抛 ErrMixedFamily", "通过" if ok else ";".join(problems))


SCENARIOS = (
    ("parse", "ipv4-ipv6", scenario_parse_ipv4_ipv6),
    ("parse", "reject-bad", scenario_parse_reject_bad),
    ("union", "overlapping", scenario_union_overlapping),
    ("union", "adjacent", scenario_union_adjacent),
    ("tocidrs", "cover-correctness", scenario_tocidrs_cover_correctness),
    ("tocidrs", "minimal-count", scenario_tocidrs_minimal_count),
    ("tocidrs", "ascending", scenario_tocidrs_ascending),
    ("diff", "correctness", scenario_diff_correctness),
    ("diff", "normalized", scenario_diff_normalized),
    ("family", "mixed-rejected", scenario_family_mixed_rejected),
)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="check.py")
    parser.add_argument("-list", dest="list_scenarios", action="store_true",
                        help="列出全部场景后退出")
    parser.add_argument("--only", dest="only", default=None,
                        help="只运行指定组")
    args = parser.parse_args(argv)

    if args.list_scenarios:
        for group, name, _func in SCENARIOS:
            print("%s/%s" % (group, name))
        return 0

    selected = [s for s in SCENARIOS if args.only is None or s[0] == args.only]
    passed = 0
    for group, name, func in selected:
        try:
            ok, expected, actual = func()
        except NotImplementedError:
            ok, expected, actual = False, "已实现", "NotImplementedError"
        except Exception as exc:  # noqa: BLE001
            ok, expected, actual = False, "无异常", "%s: %s" % (type(exc).__name__, exc)
        if ok:
            passed += 1
            print("PASS %s/%s" % (group, name))
        else:
            print("FAIL %s/%s  期望=%s 实际=%s" % (group, name, expected, actual))

    print("结果：通过 %d/%d" % (passed, len(selected)))
    return 0 if selected and passed == len(selected) else 1


if __name__ == "__main__":
    sys.exit(main())
