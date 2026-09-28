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
