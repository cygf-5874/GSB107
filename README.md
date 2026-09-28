# netcidr

`netcidr` 是一个纯标准库的 **IP 区间代数**库：把 CIDR 表示的地址集合铺成
半开整数区间，再做合并、包含、差集，以及「用最少的 CIDR 覆盖一个区间集合」的
前缀分解。IPv4 与 IPv6 用同一套整数区间表示。

- 语言 / 运行：Python 3，只用标准库（`ipaddress` 用于地址文本解析），无第三方依赖。
- 自检：`bash scripts/check.sh`（内部调用 `check/check.py`，那是固定验收程序，**别改**）。
- 起点：`netcidr.py` 只有类型与签名，方法体全抛 `NotImplementedError`；`python3 -c "import netcidr"` 通过。

## 怎么跑

```bash
python3 -c "import netcidr"             # 退出码 0
bash scripts/check.sh                    # 固定验收（10 个场景）
bash scripts/check.sh -list              # 列出全部场景
bash scripts/check.sh --only tocidrs     # 只跑一组
```

前提：Python 3.7+（本仓库按 3.13 验证）。不引入任何第三方依赖。

## 目录

```
.
├── .gitattributes
├── .gitignore
├── README.md
├── PROMPT.md             本题的 User Prompt（逐字）
├── errors.py             ErrBadCidr / ErrMixedFamily（已给全，勿改名字与含义）
├── netcidr.py            类型与签名（方法体抛 NotImplementedError，待实现）
├── check/check.py        固定验收程序：10 个场景（勿改）
└── scripts/check.sh      薄封装
```

## 对外契约（10 条）

1. `parse(cidr: str) -> Range`：解析 `a.b.c.d/len` 或 `addr/len`（含 IPv6），返回半开区间 `[lo, hi)` 的**整数**表示；
   非法输入抛 `ErrBadCidr`。
2. `RangeSet` 内部表示为一组**互不相交且按 lo 升序**的半开区间（整数对）；
   空集合用空列表表示。
3. `union(items: list[str]) -> RangeSet`：合并输入的 CIDR 集合，结果必须是**规范形式**（见第 4 / 5 条）。
4. **规范化**：相邻或重叠区间必须合并；合并后**不得**出现可由「更短前缀」等价表示的两个相邻块
   （即不做超网聚合，只做区间合并）。
5. **最小 CIDR 覆盖** `to_cidrs(rs: RangeSet) -> list[str]`：输出覆盖同一集合的 CIDR 列表，
   要求**条数最少**且**按 lo 升序**（这是本科目的核心：区间 → 最少前缀分解）。
6. `contains(rs, x: int) -> bool` 与 `contains_range(rs, cidr: str) -> bool`（后者判断整个 CIDR 是否被包含）。
7. `difference(a: RangeSet, b: RangeSet) -> RangeSet`：区间差集，结果同样规范化。
8. **IPv4 与 IPv6 不得混用**：同一 `RangeSet` 里出现两种地址族抛 `ErrMixedFamily`。
9. 边界：`/0`（全空间）、`/32`（单地址）、`/128`、空集合的 `to_cidrs` 返回 `[]`、
   空集合的 `contains` 返回 `False`。
10. **禁止**用 `ipaddress` 的 `collapse_addresses` / `summarize_address_range` / `supernet`：
    这三个 API 直接给出了第 5 条的答案；地址的**文本解析**可以用 `ipaddress.ip_address`，
    但区间代数（合并、差集、最小覆盖）必须自己写。结果与 `dict` 迭代顺序无关。

> 已导出的类型 `Range` / `RangeSet` 的字段与内部表示（`RangeSet.ranges`、`RangeSet.family`）
> 是契约的一部分；`errors.py` 里两个错误类的名字与含义不得改。可以新增模块 / 辅助函数。

## 验收

`check/` 是固定验收程序，**不要修改**。场景分五组，共 10 个：

| 组 | 场景 | 覆盖 |
| --- | --- | --- |
| `parse` | `ipv4-ipv6` | 契约 1、9：IPv4/IPv6 解析、`/0`、`/32`、`/128` |
| `parse` | `reject-bad` | 契约 1：非法输入 → `ErrBadCidr` |
| `union` | `overlapping` | 契约 2、3、6：重叠合并、`contains` / `contains_range` |
| `union` | `adjacent` | 契约 2、4：相邻合并、结果升序 |
| `tocidrs` | `cover-correctness` | 契约 5：覆盖正确且与逐条解析一致 |
| `tocidrs` | `minimal-count` | 契约 5：条数最少（非对齐边界不多拆） |
| `tocidrs` | `ascending` | 契约 5、9：按 lo 升序、空集合边界 |
| `diff` | `correctness` | 契约 7：差集覆盖正确 |
| `diff` | `normalized` | 契约 7：结果规范化且不改入参 |
| `family` | `mixed-rejected` | 契约 8：混用地址族 → `ErrMixedFamily` |

```bash
python3 -c "import netcidr"   # 退出码 0
bash scripts/check.sh          # 退出码 0，10 个场景全过
```

## User Prompt

```
需要四个能力，缺一不可：合并、包含、差集、区间化。netcidr 是 Python 3 的
地址区间代数库，只用标准库，构建不需要额外步骤，
自检走 `scripts/check.sh`（`check/` 是固定验收程序，别改）。

`netcidr.py` 现在只有类型和签名，方法体全抛 `NotImplementedError`；`errors.py` 里两个错误类已经给全。

任务：按 README「对外契约」的 10 条实现，让固定件全过。

验收：
- python3 -c "import netcidr" 退出码 0；
- python3 check/check.py 退出码 0，10 个场景全过（parse 2 + union 2 + tocidrs 3 + diff 2 + family 1）。

约束：
1. 不改 `check/`、不改 `errors.py` 里错误类的名字与含义；可以新增模块。
2. 地址的文本解析可以用标准库的 `ipaddress.ip_address`，但**不许**用
   `collapse_addresses`、`summarize_address_range`、`supernet` —— 这三条直接给出了答案，
   区间代数要自己写。
3. 只用标准库，不许引入任何第三方包。
4. 结果必须与 `dict` 迭代顺序无关。
```
